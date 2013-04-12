from pymeta.grammar import OMeta
import json
import os

def compile(source):
	return Translator.parse(Grammar.parse(source))

grammar_path = os.path.join(os.path.dirname(__file__), 'grammar.ometa')
pyva_grammar = open(grammar_path, 'r').read()
def p(s):
	print s

class Grammar(OMeta.makeGrammar(pyva_grammar, {'p': p})):
	keywords = set(('and', 'as', 'break', 'case', 'catch', 'class', 'continue',
		'def', 'default', 'del', 'delete', 'do', 'elif', 'else', 'except',
		'finally', 'for', 'function', 'if', 'in', 'instanceof',
		'new', 'not', 'or', 'pass', 'raise', 'return', 'switch',
		'throw', 'til', 'to', 'try', 'var', 'void', 'while', 'with',
		'yield',))
	hex_digits = '0123456789abcdef'

	def __init__(self, *args, **kwargs):
		super(Grammar, self).__init__(*args, **kwargs)
		self.parenthesis = 0
		self.parenthesis_stack = []
		self.indent_stack = [0]

	def enter_paren(self):
		self.parenthesis += 1

	def leave_paren(self):
		self.parenthesis -= 1

	def enter_deflambda(self, indent):
		self.indent_stack.append(indent)
		self.parenthesis_stack.append(self.parenthesis)
		self.parenthesis = 0

	def leave_deflambda(self):
		self.indent_stack.pop()
		self.parenthesis = self.parenthesis_stack.pop()

	def get_indent(self):
		start = self.input.position
		for index in reversed(range(self.input.position)):
			char = self.input.data[index]
			if char == '\n':
				return start - (index + 1)
			elif char != ' ':
				start = index
		return 0

	def dedent(self):
		# A dedent comes after a '\n'. Put it back, so the outer line
		# rule can handle the '\n'
		self.indent_stack.pop()
		input = self.input.prev()
		if input.head()[0] == '\n':
			self.input = input

	def is_keyword(self, keyword):
		return keyword in self.keywords

translator_path = os.path.join(os.path.dirname(__file__), 'translator.ometa')
pyva_translator = open(translator_path, 'r').read()
class Translator(OMeta.makeGrammar(pyva_translator, {'p': p, 'json': json})):
	op_map = {
		'not': '!',
	}
	binop_map = {
		'or': '||',
		'and': '&&',
		'is': '===',
		'is not': '!==',
	}
	name_map = {
		'None': 'null',
		'True': 'true',
		'False': 'false',
		'self': 'this',
		'int': 'parseInt',
		'float': 'parseFloat',
		'bool': '!!',
		'tuple': 'list',
		'unicode': 'str',
	}

	#class variable indicating whether comments are allowed or not
	allowcomments = False

	def __init__(self, *args, **kwargs):
		super(Translator, self).__init__(*args, **kwargs)
		self.indentation = 0
		self.local_vars = set()
		self.nonlocal_vars = set()
		self.global_vars = set()
		self.var_stack = []
		self.temp_var_id = 0

	@classmethod
	def parse(cls, *args, **kwargs):
		if 'debug_flag' in kwargs:
			#Set allowcomments to the debug flag
			cls.allowcomments = bool(kwargs['debug_flag'])
			#Remove the debug flag keyword
			del kwargs['debug_flag']
		else:
			cls.allowcomments = False
		return super(Translator, cls).parse(*args, **kwargs)

	def get_name(self, name):
		if name == 'self' and name not in self.global_vars:
			return name
		return self.name_map.get(name, name)

	def make_temp_var(self, name, prefix='_$tmp'):
		self.temp_var_id += 1
		return '%s%s_%s' % (prefix, self.temp_var_id, name)

	def indent(self):
		self.indentation += 1
		return self.indentation

	def dedent(self):
		self.indentation -= 1

	def is_pure_var_name(self, var):
		return '.' not in var and '[' not in var

	def is_list_var_name(self, var):
		return var[0] == '[' and var[-1] == ']'

	def __register_var(self, var):
		if self.is_pure_var_name(var) and \
				var not in self.global_vars and \
				var not in self.nonlocal_vars:
			self.local_vars.add(var)

	def __get_var_list(self, var_list_str):
		var_names = var_list_str[1:-1].split(',')
		var_names = [var_name.strip() for var_name in var_names]
		return var_names

	def make_comment(self, c):
		if self.allowcomments:
			return '//%s' % c
		else:
			return None

	def make_stmts(self, ss):
		"""
		Filter out None statements - these are currently filtered out comments
		"""
		return [s for s in ss if s is not None]

	def make_eq(self, var, val):
		indent = '  ' * self.indentation
		if self.is_list_var_name(var):
			var_names = self.__get_var_list(var)
			var_str = '_$rapyd_tuple$_ = %s' % val
			for i in xrange(len(var_names)):
				var_str += ';\n%s%s = %s' % (indent, var_names[i],
											  '_$rapyd_tuple$_['+str(i)+']')
		else:
			var_str = '%s = %s' % (var, val)

		return var_str

	def register_var(self, var):
		if self.is_list_var_name(var):
			var_names = self.__get_var_list(var)
			self.__register_var('_$rapyd_tuple$_')
			for i in xrange(len(var_names)):
				self.__register_var(var_names[i])
		else:
			self.__register_var(var)

	def register_nonlocals(self, vars):
		for var in vars:
			if self.is_pure_var_name(var) and var not in self.global_vars:
				self.nonlocal_vars.add(var)
				self.local_vars -= set([var])

	def register_globals(self, vars):
		self.global_vars.update([var for var in vars if self.is_pure_var_name(var)])
		self.local_vars -= self.global_vars
		self.nonlocal_vars -= self.global_vars

	def push_vars(self):
		self.var_stack.append((self.local_vars, self.nonlocal_vars, self.global_vars))
		self.local_vars = set()
		self.nonlocal_vars = set()
		self.global_vars = set()

	def translate_cmp(self, x, op, y):
		if op == 'not in':
			#special case
			return '!(%s in %s)' % (x, y)
		else:
			return '(%s %s %s)' % (x, self.binop_map.get(op, op), y)

	def make_chained_cmp(self, l, r):
		"""
		build a chained comparison - this is not intended to handle
		single comparions because it adds unnecessary extra variables
		"""
		comps = iter(r)
		comp = comps.next()

		final_comp = self.translate_cmp(l, comp[0], comp[1])
		prev_var = comp[1]

		for comp in comps:
			final_comp = '%s && %s' % \
				(final_comp, self.translate_cmp(prev_var, comp[0], comp[1]))
			prev_var = comp[1]
		return '(%s)' % final_comp

	def pop_vars(self):
		self.local_vars, self.nonlocal_vars, self.global_vars = self.var_stack.pop()

	def make_block(self, stmts, indentation):
		indentstr = '  ' * indentation
		line_list = []
		for stmt in stmts:
			if stmt.startswith('//'):
				line_list.append(stmt)
			else:
				line_list.append('%s%s' % (indentstr, stmt))
		return '{\n%s\n%s}' % ('\n'.join(line_list), '  ' * (indentation - 1))

	def make_func_block(self, stmts, indentation):
		if self.local_vars:
			vars_str = ', '.join(sorted(self.local_vars))
			var_stmt = ['var %s;' % vars_str]
		else:
			var_stmt = []
		return self.make_block(var_stmt+stmts, indentation)

	def make_dict(self, items, indentation):
		indentstr = '  ' * indentation
		sep = ',\n%s' % indentstr
		return '{\n%s%s\n%s}' % (indentstr, sep.join(items), '  ' * (indentation - 1))

	def comments_str(self, raw_comments):
		comments = []
		if self.allowcomments:
			for comment in raw_comments:
				if comment and comment[0]=='comment':
					comments.append('//%s' % comment[1])

		if comments:
			return '\n%s\n%s' % ('\n'.join(comments), '  '  * self.indentation)
		else:
			return ''

	def make_if(self, cond, block, elifexprs, elseblock):
		expr = ['if (%s) %s' % (cond, block)]
		for elifexpr in elifexprs:
			comments = self.comments_str(elifexpr[0])
			expr.append('%selse if (%s) %s' % (comments, elifexpr[1], elifexpr[2]))
		if elseblock and elseblock[1]:
			comments = self.comments_str(elseblock[0])
			expr.append('%selse %s' % (comments, elseblock[1]))
		return ' '.join(expr)

	def make_try(self, body, catch, fin):
		expr = ['try %s' % body]
		if catch is not None:
			expr.append('catch(%s) %s' % (catch[1], catch[2]))
		if fin is not None:
			expr.append('finally %s' % fin[1])
		return ' '.join(expr)

	def make_for(self, var, data, body):
		indentstr = '  ' * self.indentation
		datavar = self.make_temp_var('data')
		lenvar = self.make_temp_var('len')
		index = self.make_temp_var('index')
		unpack_str = ''
		if self.is_list_var_name(var):
			RAPYD_PACKED_TUPLE = '_$rapyd$_tuple'
			var_list = self.__get_var_list(var)
			unpack_str = ''
			for i in xrange(len(var_list)):
				unpack_str += '%s%s = %s[%d];\n' % \
				(indentstr + '  ', var_list[i], RAPYD_PACKED_TUPLE, i)
			var = RAPYD_PACKED_TUPLE
		init = 'var %s = _$rapyd$_iter(%s);\n%svar %s = %s.length;\n%s' % (
			datavar, data, indentstr, lenvar, datavar, indentstr)
		body = body.replace('{', '{\n%s%s = %s[%s];\n%s'
							% (indentstr + '  ', var, datavar, index, unpack_str), 1)
		return '%sfor (var %s = 0; %s < %s; %s++) %s' % (init, index, index, lenvar,
														 index, body)

	def temp_var_or_literal(self, name, var, init):
		"""
		Returns either the literal if it's a literal or a temporary variable
		storing the non-literal in addition to regitering the temporary with
		init.
		"""
		if var[0]:
			# Literal
			return var[1]
		temp = self.make_temp_var(name)
		init.append('%s = %s' % (temp, var[1]))
		return temp

	def make_for_range(self, var, for_range, body):
		# for_range is a list of tuples (bool:literal, str:js_code)
		indentstr = '  ' * self.indentation
		stepstr = '%s++' % var
		init = []
		if len(for_range) == 1:
			start = 0
			end = self.temp_var_or_literal('end', for_range[0], init)
		else:
			start = for_range[0][1]
			end = self.temp_var_or_literal('end', for_range[1], init)
			if len(for_range) == 3:
				step = self.temp_var_or_literal('step', for_range[2], init)
				stepstr = '%s += %s' % (var, step)

		initstr = ''
		if init:
			initstr = 'var %s;\n%s' % (', '.join(init), indentstr)

		return '%sfor (%s = %s; %s < %s; %s) %s' % (initstr, var, start, var,
													end, stepstr, body)

	def make_for_reversed_range(self, var, for_range, body):
		indentstr = '  ' * self.indentation
		if len(for_range) == 1:
			return '%s = %s;\n%swhile (%s--) %s' % (var, for_range[0][1], indentstr,
													var, body)

		init = []
		start = for_range[1][1]
		end = self.temp_var_or_literal('end', for_range[0], init)
		if len(for_range) == 3:
			step = self.temp_var_or_literal('step', for_range[2], init)
			stepstr = '%s -= %s' % (var, step)
		else:
			stepstr = '%s--' % var

		initstr = ''
		if init:
			initstr = 'var %s;\n%s' % (', '.join(init), indentstr)

		return '%sfor (%s = (%s) - 1; %s >= %s; %s) %s' % (
			initstr, var, start, var, end, stepstr, body)

	def make_func(self, name, args, body):
		if name:
			name = self.get_name(name[1])
			self.register_var(name)
			func = '%s = function' % name
			body += ';'
		else:
			func = 'function'
		if args and args[0] == self.get_name('self'):
			args = args[1:]
		return '%s(%s) %s' % (func, ', '.join(args), body)

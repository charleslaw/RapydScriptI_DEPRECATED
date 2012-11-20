#!/usr/bin/env python

import sys, re, os
import string
from grammar import Grammar, Translator, compile
from codecheck import verify_code

class_list = []
global_object_list = {}
dependency_list = [] #TODO: build this and append files in required order
arg_dump = []
js_map = {'None' : 'null', 'True' : 'true', 'False' : 'false'}

class State:
	def __init__(self):
		self.class_name = None
		self.parent = None
		self.indent = ''
		self.methods = []
		self.inclass = False
		self.incomment = False

imported_files = []
def import_module(line, output, handler):
	tokens = line.split()
	if not ((len(tokens) == 2 and tokens[0] == 'import') or \
			(len(tokens) == 4 and tokens[0] == 'from' and tokens[2] == 'import')):
		raise ImportError("Invalid import statement: %s" % line.strip())
	
	if tokens[1] not in imported_files:
		try:
			imported_files.append(tokens[1])
			parse_file(tokens[1].replace('.', '/') +'.pyj', output, handler)
		except IOError:
			raise ImportError("Can't import %s, module doesn't exist" % tokens[1])
		
def add_new_keyword(line):
	#check to see if we need to plug in the 'new' keyword
	#if line.find('=') != -1:
	#	obj_type = line[line.index('=')+1:].lstrip().split('(')[0]
	#	if obj_type in class_list:
	#		return line.replace('=', '= new ')
	
	# this regex version is more durable for arrays, etc., but I'm not completely convinced it's flawless
	# yet so I will leave the old one in
	# not every line containing a :/=/return will need this, but it's much better than running a regex on
	# every line of code
	for obj_type in class_list:
		if obj_type in line:
			# adds a new keyword to the class creation: 'Class(...)', unless it's inside of a string
			line = re.sub(r'^([^\'"]*(?:([\'"])[^\'"]*\2)*[^\'"]*)\b(%s\s*\()' % obj_type, r'\1new \3', line)
	return line

def convert_to_js(line):
	"""
	directly convert some code to js
	"""
	line = add_new_keyword(line)
	line = compile(line).strip()
	return line

def convert_list_comprehension(line):
	# replaces list comprehension in a given line with equivalent logic using map() + filter()
	# combination from stdlib.
	
	# this will be slightly inefficient for cases when calling a function on iterated element
	# due to creation of an extra function call, but the performance impact is negligible and
	# seems cleaner than introducing additional special cases here
	
	# Python requires fixed-width look-aheads/look-behinds, so let's 'fix' them
	look_behind = re.findall(r'\[\s*.+\sfor\s+', line)
	# just because we're here, doesn't mean it was a list comprehension, it could have been
	# a regular for loop
	if look_behind:
		look_behind = look_behind[0]
		#get the text before the look_behind string
		line_start = re.split(re.escape(look_behind), line)[0]
	else:
		return line

	look_ahead = re.findall(r'\s*\]', line)
	if look_ahead:
		look_ahead = look_ahead[-1]
		#get the text after the look_ahead string
		line_end = re.split(re.escape(look_ahead), line)[-1]
	else:
		return line

	# first, expand the filter out, this stage will do the following:
	# before:	a = [stuff(i) for i in array if something(i)]
	# after:	a = [stuff(i) for i in array.filter(JS('function(i){return something(i);}'))]
	# if there is no filter/if, this stage will have no effect
	filter_groups = re.search(\
		r'(?<=%s)([A-Za-z_$][A-Za-z0-9_$]*)(\s+in\s+)(.*)\s+if\s+(.*)(?=%s)' \
		% (re.escape(look_behind), re.escape(look_ahead)), line)
	if filter_groups:
		#parse any js code
		return_code = convert_to_js('return %s' % filter_groups.group(4))

		#Build the line using the regex groups and the converted return code
		line = '%s%s%s%s%s.filter(JS("function(%s){%s}"), self)%s%s' % \
			(line_start, look_behind, filter_groups.group(1), 
			filter_groups.group(2), filter_groups.group(3),
			filter_groups.group(1), return_code, look_ahead, line_end)

	# now expand the map out, this stage will do the following:
	# before:	a = [stuff(i) for i in array.filter(JS('function(i){return something(i);}'))]
	# after: 	a = array.filter(JS('function(i){return something(i);}')).map(JS('function(i){return stuff(i);}'))
	map_groups = re.search(\
		r'\[\s*(.+)\sfor\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+in\s+(.*)\s*\]', line)
	if map_groups:
		#parse any js code
		return_code = convert_to_js('return %s' % map_groups.group(1))

		#Build the line using the regex groups and the converted return code
		line = '%s%s.map(JS("function(%s) {%s}"), self)%s' % \
			(line_start, map_groups.group(3), map_groups.group(2),
			return_code, line_end)
	return line

basic_indent = ''
def get_indent(line):
	global basic_indent
	indent = line[:len(line)-len(line.lstrip())].rstrip('\n') # in case of empty line, remove \n
	if not basic_indent:
		basic_indent = indent
	return indent

def js_convert(value):
	if value in js_map.keys():
		return js_map[value]
	else:
		return value

def get_args(line, isclass=True):
	# get arguments and sets arg_dump as needed (for handling optional arguments)
	args = line.split('(')[1].split(')')[0].split(',')
	for i in range(len(args)):
		args[i] = args[i].strip()
		if args[i].find('=') != -1:
			assignment = args[i].split('=') 
			value = js_convert(assignment[1].strip())
			args[i] = assignment[0].strip()
			arg_dump.append('JS(\'if (typeof %s === "undefined") {%s = %s};\')\n' % (args[i], args[i], value))
	
	# remove "fake" arguments
	args = filter(None, args)
	
	if isclass:
		args.pop(0)
	
	return args

def parse_fun(line, isclass=True):
	method_name = line.lstrip().split()[1].split('(')[0]
	method_args = get_args(line, isclass)
	return method_name, method_args

def get_arg_dump(line):
	global arg_dump
	output = ''
	if arg_dump:
		indent = get_indent(line)
		for var in arg_dump:
			output += indent+var #dump optional variable declarations
		arg_dump = []
	return output

def set_args(args):
	#return a string converting argument list to string
	return '(%s):\n' % ', '.join(args)

def to_star_args(args):
	# return arg array such that it can be used in 'apply', assuming last argument is *args
	if args:
		star = args.pop().lstrip('*')
		
		# we can't just use str(), since every argument is already a string
		arg_arr = '[%s]' % ', '.join([i for i in args])
		return '%s.concat(%s)' % (arg_arr, star)
	return ''

def parse_multiline(line):
	if len(line) >= 2 and line[-2] == '\\':
		return line.replace('\\\n', ''), 1
	return line, 0

def invokes_method_from_another_class(line):
	tag = line.strip()
	# remove quoted content, so that strings can't falsely trigger our method invoking logic
	tag = re.sub(r'([\'"])(?:(?!\1)\\?.)*\1','', tag)
	for item in class_list:
		found_loc = tag.find('%s.' % item)
		if found_loc != -1 and (found_loc == 0 or (tag[found_loc-1] not in string.letters and tag[found_loc-1] != '_')):
			return True
	return False

def wrap_chained_call(line):
	# this logic allows some non-Pythonic syntax in favor of JavaScript-like function usage (chaining, and calling anonymous function without assigning it)
	return 'JS("<<_rapydscript_bind_>>%s;")\n' % line.rstrip().replace('"', '\\"')

def bind_chained_calls(source):
	# this logic finalizes the above logic after PyvaScript has run
	source = re.sub(r';\s*\n*\s*<<_rapydscript_bind_>>', '', source, re.MULTILINE) # handle semi-colon binding
	return re.sub(r'}\s*\n*\s*<<_rapydscript_bind_>>', '}', source, re.MULTILINE) # handle block binding

# I was lazy here, eventually we want to have this be an optional parameter passed to constructor from caller instead of a global
internal_var_reserved_offset = 0
class ObjectLiteralHandler:

	def __init__(self):
		self.object_literal_function_defs = {}
	
	def start(self, source):
		#PyvaScript breaks on function definitions inside dictionaries/object literals
		#we rip them out and translate them independently, replacing with temporary placeholders
		global internal_var_reserved_offset
		items = re.findall('(?P<indent>\n\s*)["\'][A-Za-z0-9_$]+["\']+\s*:\s*(?P<main>def\s*\([A-Za-z0-9_=, ]*\):.*?),(?=((?P=indent)(?!\s))|\s*})', source, re.M + re.DOTALL)
		offset = 0
		for count, item in enumerate(items):
			hash_val = '$rapyd_internal_var%d' % (count+internal_var_reserved_offset)
			
			#apply proper indent, split function into pythonic multi-line version and convert it
			#we do recursive substitution here to allow object literal declaration inside other functions
			function = item[1].replace(item[0],'\n').replace('\r', '')
			handler = ObjectLiteralHandler()
			function = handler.start(function)
			function = Translator.parse(Grammar.parse(function)).replace('\n', item[0]).rstrip()
			function = handler.finalize(function)
			
			self.object_literal_function_defs[hash_val] = function
			source = source.replace(item[1], hash_val)
			offset += 1
		internal_var_reserved_offset += offset
		return source
		
	def finalize(self, source):
		for hash_key in self.object_literal_function_defs.keys():
			source = source.replace(hash_key, self.object_literal_function_defs[hash_key])
		source = source.replace('\t', '  ') # PyvaScript uses 2 spaces as indent, minor
		return source
	
global_buffer = ''
def write_buffer(input):
	global global_buffer
	global_buffer += input
	
def dump_buffer(file):
	global global_buffer
	file.write(global_buffer)
	file.write('\n')
	global_buffer = ''

def parse_file(file_name, output, handler = ObjectLiteralHandler()):
	#parse a single file into global namespace
	global global_buffer
	state = State()
	need_indent = False
	post_init_dump = ''
	post_function = []
	function_indent = None
	replaced = 0
	with open(file_name, 'r') as input:
		# check for easy to spot errors/quirks we require
		if not verify_code(file_name, input, global_object_list):
			sys.exit()
	
		input.seek(0)
		line_num = -1
		for line in input:
			line_num += 1
			line = line.replace('\r','')
			#parse out multi-line comments
			lstrip_line = line.lstrip()
			if lstrip_line[:3] in ('"""', "'''"):
				state.incomment = not state.incomment
				continue
			if state.incomment:
				continue
			if function_indent == get_indent(line):
				for post_line in post_function:
					write_buffer(post_line)
				post_function = []
				function_indent = None
				#input.seek(line_num)
			if line.find('def') != -1 and line.find('def') < line.find(' and ') < line.find(':') \
			and re.match('^(\s*)(def\s*\(.*\))\s+and\s+([A-Za-z_$][A-Za-z0-9_$]*\(.*\)):$', line):
				# handle declaration and call at the same time
				groups = re.match('^(\s*)(def\s*\(.*\))\s+and\s+([A-Za-z_$][A-Za-z0-9_$]*\(.*\)):$', line).groups()
				line = groups[0] + groups[1] + ':\n'
				indentation = groups[0]
				if state.inclass:
					indentation = indentation[len(state.indent):] # dedent
				post_function.append('%s%s\n' % (indentation, wrap_chained_call('.%s' % groups[2])))
				function_indent = groups[0]
			if need_indent:
				need_indent=False
				state.indent=line.split('d')[0] #everything before 'def'
			if line[:5] == 'from ' or line[:7] == 'import ':
				import_module(line, output, handler)
				continue
			if line[:6] == 'class ':
				# class definition
				# this is where we do our 'magic', creating 'bad' Python that PyvaScript naively translates
				# into good JavaScript
				initdef = False
				state.__init__() #reset state
				state.inclass = True
				class_data = line[6:].split('(')
				if len(class_data) == 1: #no inheritance
					state.class_name = class_data[0][:-2] #remove the colon and newline from the end
				else:
					state.class_name = class_data[0]
					state.parent = class_data[1][:-3] #assume single inheritance, remove '):'
					post_init_dump += '%s.prototype = new %s()\n' % (state.class_name, state.parent)
				class_list.append(state.class_name)
				need_indent = True
			elif line[0] not in (' ', '\t', '\n'):
				#line starts with a non-space character
				if post_init_dump:
					write_buffer(post_init_dump)
					post_init_dump = ''
				state.inclass = False
				
			# convert list comprehensions
			# don't bother performing expensive regex unless the line actually has 'for' keyword in it
			if line.find(' for ') != -1:
				line = convert_list_comprehension(line)

			# handle JavaScript-like chaining
			if global_buffer and global_buffer[-1] == '\n' and lstrip_line and lstrip_line[0] == '.':
				if state.inclass:
					line = line[len(state.indent):] # dedent
				write_buffer(line.split('.')[0] + wrap_chained_call(lstrip_line))
				continue

			# process the code as if it's part of a class
			# Again, we do more 'magic' here so that we can call parent (and non-parent, removing most of
			# the need for multiple inheritance) methods.
			if state.inclass and line[:6] != 'class ':
				if line.find('def __init__') != -1:
					# constructor definition
					initdef = True
					if state.parent is not None:
						post_init_dump += '%s.prototype.constructor = %s\n' % (state.class_name, state.class_name)
					init_args = get_args(line)
					write_buffer('def %s%s' % (state.class_name, set_args(init_args)))
				elif len(line) > len(state.indent)+4 and line[len(state.indent):len(state.indent)+4] == 'def ':
					# method definition
					if not initdef:
						#assume that __init__ will be the first method declared, if it is declared
						if state.parent is not None:
							post_init_dump += '%s.prototype.constructor = %s\n' % (state.class_name, state.class_name)
							inherited = '%s.prototype.constructor.call(this);' % state.parent
						else:
							inherited = ''
						write_buffer('JS(\'%s = function() {%s};\')\n' % (state.class_name, inherited))
						initdef = True
					if post_init_dump:
						write_buffer(post_init_dump)
						post_init_dump = ''
					method_name, method_args = parse_fun(line)
					
					# handle *args for function declaration
					post_declaration = []
					if method_args and method_args[-1][0] == '*':
						count = 0
						for arg in method_args[:-1]:
							post_declaration.append('%s = arguments[%s]' % (arg, count))
							count += 1
						post_declaration.append('%s = [].slice.call(arguments, %s)' % (method_args[-1][1:], count))
						method_args = ''
					
					write_buffer('%s.prototype.%s = def%s' % (state.class_name, method_name, set_args(method_args)))
					
					# finalize *args logic, if any
					for post_line in post_declaration:
						write_buffer(get_indent(line) + post_line + '\n')
				else:
					# regular line
					if replaced:
						line = line.lstrip()
						replaced = 0
					elif len(line) > len(state.indent):
						line = line[len(state.indent):] #dedent
					line, replaced = parse_multiline(line)
					write_buffer(get_arg_dump(line))
					
					if line.find('.__init__') != -1:
						line = line.replace('.__init__(self', '.prototype.constructor.call(this')
					elif invokes_method_from_another_class(line):
						# method call of another class
						indent = get_indent(line)
						parts = line.split('.')
						parent_method = parts[1].split('(')[0]
						parent_args = get_args(line, False)
						
						if parent_args[-1][0] == '*':
							# handle *args
							line = '%s%s.prototype.%s.apply(%s, %s)' % (\
								indent,
								parts[0].strip(),
								parent_method,
								parent_args[0],
								to_star_args(parent_args[1:])+'\n')
						else:
							line = '%s%s.prototype.%s.call(%s' % (\
								indent, 
								parts[0].strip(),
								parent_method,
								set_args(parent_args)[1:-2]+'\n')
					line = line.replace('self.', 'this.')
					line = add_new_keyword(line)
					write_buffer(line)
			elif line[:6] != 'class ':
				if replaced:
					line = line.lstrip()
					replaced = 0
				line, replaced = parse_multiline(line)
				line = add_new_keyword(line)
				if line.strip()[:4] == 'def ':
					# function definition
					fun_name, fun_args = parse_fun(line, False)
					
					# handle *args for function declaration
					post_declaration = []
					if fun_args and fun_args[-1][0] == '*':
						count = 0
						for arg in fun_args[:-1]:
							post_declaration.append('%s = arguments[%s]' % (arg, count))
							count += 1
						post_declaration.append('%s = [].slice.call(arguments, %s)' % (fun_args[-1][1:], count))
						fun_args = ''
						
					write_buffer(get_indent(line)+'def %s%s' % (fun_name, set_args(fun_args)))
					
					# finalize *args logic, if any
					for post_line in post_declaration:
						write_buffer(get_indent(line) + basic_indent + post_line + '\n')
				else:
					# regular line
					
					# the first check is a quick naive check, making sure that there is a * char
					# between parentheses
					# the second check is a regex designed to filter out the remaining 1% of false
					# positives, this check is much smarter, checking that there is a ', *word)'
					# pattern preceded by even number of quotes (meaning it's unquoted)
					if line.find('(') < line.find('*') < line.find(')') \
					and re.match(r'^[^\'"]*(([\'"])[^\'"]*\2)*[^\'"]*,\s*\*.*[A-Za-z$_][A-Za-z0-9$_]*\s*\)', line):
						args = to_star_args(get_args(line, False))
						line = re.sub('\(.*\)' , '.apply(this, %s)' % args, line)
					
					write_buffer(get_arg_dump(line))
					write_buffer(line)
	if post_init_dump:
		write_buffer(post_init_dump)
		post_init_dump = ''
		
	#handler = ObjectLiteralHandler()
	global_buffer = handler.start(global_buffer)
	dump_buffer(output)
	return handler

def finalize_source(source, handler):
	g = Grammar.parse(source)

	output = Translator.parse(g)
	output = handler.finalize(output) #insert previously removed functions back in
	#PyvaScript seems to be buggy with self replacement sometimes, let's fix that
	output = re.sub(r'\bself\b', 'this', output)
	output = bind_chained_calls(output)
	return output

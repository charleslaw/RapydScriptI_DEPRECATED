#!/usr/bin/env python

import sys, re, os
import string
from grammar import Grammar, Translator, compile
from codecheck import verify_code
from exceptions import update_exception_indent_data, process_exception_line

class_list = []
global_object_list = {}
arg_dump = []

class State:
	def __init__(self, file_name):
		self.class_name = None
		self.parent = None
		self.indent = ''	# default indent marker of this file
		self.methods = []
		self.inclass = False
		self.incomment = False
		
		# file statistics
		self.file_name = file_name
		self.line_num = 0
		self.line_content = ''
		self.multiline_start_num = -1
		self.multiline_content = ''
	
	def reset(self):
		self.__init__(self.file_name)

imported_files = []
def import_module(line, output, handler):
	tokens = line.split()
	if not ((len(tokens) == 2 and tokens[0] == 'import') or \
			(len(tokens) == 4 and tokens[0] == 'from' and tokens[2] == 'import')):
		raise ImportError("Invalid import statement: %s" % line.strip())
	
	if tokens[1] not in imported_files:
		try:
			parse_file(tokens[1].replace('.', '/') +'.pyj', output, handler)
		except IOError:
			# couldn't find the file in local directory, check RapydScript lib directory
			cur_dir = os.getcwd()
			try:
				# we have to rely on __file__, because cwd could be different if invoked by another script
				os.chdir(os.path.dirname(__file__))
				parse_file(tokens[1].replace('.', '/') +'.pyj', output, handler)
			except IOError:
				raise ImportError("Can't import %s, module doesn't exist" % tokens[1])
			finally:
				os.chdir(cur_dir)
		imported_files.append(tokens[1])
		
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
			line = re.sub(r'^([^\'"]*(?:([\'"])[^\'"]*\2)*[^\'"]*)(?=\b|\B\$)(%s\s*\()' % re.escape(obj_type), r'\1new \3', line)
	return line

def convert_to_js(line):
	"""
	Directly convert some code to js, useful for compiling a chunk of code that PyvaScript
	can't handle itself.
	"""
	line = add_new_keyword(line)
	line = compile(line).strip()
	return line

def convert_list_comprehension(line):
	"""
	Replace list comprehension in a given line with equivalent logic using map() + filter()
	combination from stdlib.
	
	this will be slightly inefficient for cases when calling a function on iterated element
	due to creation of an extra function call, but the performance impact is negligible and
	seems cleaner than introducing additional special cases here
	"""
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

js_map = {'None' : 'null', 'True' : 'true', 'False' : 'false'}
def convert_keyword_to_js(value):
	if value in js_map.keys():
		return js_map[value]
	else:
		return value

def get_args(line, isclass=True, isdef=True):
	# get arguments and sets arg_dump as needed (for handling optional arguments)
	args = line.split('(', 1)[1].rsplit(')', 1)[0].split(',')
	for i in range(len(args)):
		args[i] = args[i].strip()
		if isdef and args[i].find('=') != -1:
			assignment = args[i].split('=') 
			value = convert_keyword_to_js(assignment[1].strip())
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
	"""
	Return a string converting argument list to string
	"""
	return '(%s):\n' % ', '.join(args)

def to_star_args(args):
	"""
	Return arg array such that it can be used in 'apply', assuming last argument is *args
	"""
	if args:
		star = args.pop().lstrip('*')
		
		# we can't just use str(), since every argument is already a string
		arg_arr = '[%s]' % ', '.join([i for i in args])
		return '%s.concat(%s)' % (arg_arr, star)
	return ''

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


def make_exception_updates(line, lstrip_line, exception_stack, state_indent):

	if len(exception_stack) > 0:
		exception_info = exception_stack[-1]
	else:
		exception_info = None

	# Get information about the current indent (account for class's)
	indent = get_indent(line)
	indent_size = len(indent) - len(state_indent)


	# Update any indent information
	if exception_info and 'if_block_indent' not in exception_info:
		exception_info = update_exception_indent_data(exception_info, indent_size, line[0], exception_stack)


	# Print exception info to the buffer
	if exception_info:
		exceptions = exception_info['exceptions']
		
		if 'printed' in exception_info and not exception_info['printed']:
			exception_info['printed'] = True
			
			write_str = exception_info['if_block_indent']
			if not exception_info['first_exception']:
					write_str += 'el'
			if exceptions:
				# add the first exception
				write_str += 'if isinstance(%s, %s)' % (exception_info['exception_var'], exceptions[0])
				for exception_name in exceptions[1:]:
					write_str += ' or \\\n%sisinstance(%s, %s)' % \
							(exception_info['code_indent'], exception_info['exception_var'], exception_name)
				write_buffer('%s:\n' % write_str)
			elif not exception_info['first_exception']:
				# printing el+se (%sse) to the output
				write_buffer('%sse:\n' % write_str)

			# set any variables that the user has specified
			if exception_info and exception_info['var_name']:
				write_buffer('%s%s = %s\n'% \
				(exception_info['code_indent'], exception_info['var_name'], exception_info['exception_var']))

	# Print and remove exited exceptions
	# Test whitespace to see if we got ouside an except block
	is_except_line = lstrip_line.startswith('except')
	for i in xrange(len(exception_stack)-1, -1, -1):
		# Exited an except block if:
		# - current indent < exception indent
		# - current indent == exception indent AND isn't catching another exception in a try block
		if (indent_size < exception_stack[i]['source_indent']) or \
				(indent_size == exception_stack[i]['source_indent'] and not is_except_line):
			
			exited_exception = exception_stack.pop(-1)
			if exited_exception['exceptions']:
				# if we were catching specific exceptions, throw any exceptions that were not caught
				write_buffer('%selse:\n%sraise %s\n' % \
							(exited_exception['if_block_indent'],
							exited_exception['code_indent'],
							exited_exception['exception_var']))
		else:
			# did not exit the except block, so stop trying
			break
	
	# Update the exception information and update the line with any neccesary added indents
	line, exception_stack = process_exception_line(line, indent, indent_size, is_except_line,
										exception_stack, exception_info)

	lstrip_line = line.lstrip()
	return line, lstrip_line, exception_stack


class ObjectLiteralHandler:

	def __init__(self, offset=0):
		self.object_literal_function_defs = {}
		self.starting_offset = self.offset = offset
	
	def start(self, source):
		# PyvaScript breaks on function definitions inside dictionaries/object literals
		# we rip them out and translate them independently, replacing with temporary placeholders
		items = re.findall('(?P<indent>\n\s*)["\'][A-Za-z0-9_$]+["\']+\s*:\s*(?P<main>def\s*\([A-Za-z0-9_=, ]*\):.*?),(?=((?P=indent)(?!\s))|\s*})', source, re.M + re.DOTALL)
		offset = 0
		for count, item in enumerate(items):
			hash_val = '$rapyd$_internal_var%d' % (count+self.offset)
			
			# apply proper indent, split function into pythonic multi-line version and convert it
			# we do recursive substitution here to allow object literal declaration inside other functions
			function = item[1].replace(item[0],'\n').replace('\r', '')
			handler = ObjectLiteralHandler(self.offset)
			function = handler.start(function)
			function = Translator.parse(Grammar.parse(function)).replace('\n', item[0]).rstrip()
			function = handler.finalize(function)
			
			self.object_literal_function_defs[hash_val] = function
			source = source.replace(item[1], hash_val)
			offset += 1 + handler.offset - handler.starting_offset
		self.offset += offset
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
	# parse a single file into global namespace
	global global_buffer
	state = State(file_name)
	need_indent = False
	exception_stack = []
	post_init_dump = ''
	post_function = []	# store 'to-do' logic to perform after function definition
	function_indent = None
	
	with open(file_name, 'r') as input:
		# check for easy to spot errors/quirks we require
		if not verify_code(file_name, input, global_object_list):
			sys.exit()
	
		input.seek(0)
		for line in input:
			state.line_num += 1
			state.line_content = line

			# stage 0: standardize input
			# stage 0: stitching multi-line logic and multi-line strings together
			# stage 1: strip empty and doc-string lines, perform any 'to-do' logic inferred from previous line
			# stage 2: processing/interpreting the line
			
			# stage 0:
			# standardize input
			# convert DOS to UNIX format (handles files written in Windows)
			line = line.replace('\r','')
			
			# stage 1:
			# stitch together lines ending with \
			if not state.multiline_content:
				state.multiline_start_num = -1
			else:
				# continuing, strip indent
				line = line[len(get_indent(line)):]
			if len(line) >= 2 and line[-2] == '\\':
				# start/continue stitching
				if not state.multiline_content:
					# just started, remember the line
					state.multiline_start_num = state.line_num
				line = line[:-2]
				state.multiline_content += line
				continue
			else:
				# finished stitching
				line = state.multiline_content + line
				state.multiline_content = ''
					
			# stage 2:
			# add an extra indent if needed, strip out 'blank' lines, perform post-function-defition logic
			lstrip_line = line.lstrip()
			is_nonempty_line = len(lstrip_line) > 1 or \
				len(lstrip_line) == 1 and lstrip_line[0] != '\n'
			# parse out multi-line comments
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
			
			# TODO: Charles, this logic was originally before stage 1, NO interpretation logic should ever happen
			# before stage 3, I moved it further down but didn't analyze it in more detail, it's possible there
			# is other logic in stage 3 that should have priority over this, please look into it when you
			# have the time
			# Convert an except to the format accepted by Pyvascript
			is_except_line = False
			if lstrip_line.startswith('except') or \
					lstrip_line.startswith('finally'):
				is_except_line = True
			
			if is_except_line or (exception_stack and is_nonempty_line):
				line, lstrip_line, exception_stack = \
					make_exception_updates(line, lstrip_line,
										   exception_stack, state.indent)
			
			# stage 3:
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
				state.reset()
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
				if line.lstrip()[:12] == 'def __init__':
					# constructor definition
					initdef = True
					if state.parent is not None:
						post_init_dump += '%s.prototype.constructor = %s\n' % (state.class_name, state.class_name)
					init_args = get_args(line)
					write_buffer('def %s%s' % (state.class_name, set_args(init_args)))
				elif line[:len(state.indent)+4] == state.indent + 'def ':
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
					line = line[len(state.indent):] # dedent by 1 because we're inside a class
					write_buffer(get_arg_dump(line))
					
					if line.find('.__init__') != -1:
						line = line.replace('.__init__(', '.prototype.constructor.call(')
					elif invokes_method_from_another_class(line):
						# method call of another class
						indent = get_indent(line)
						parts = line.split('.')
						parent_method = parts[1].split('(')[0]
						parent_args = get_args(line, False)
						
						if parent_args[-1][0] == '*':
							# handle *args
							line = '%s%s.prototype.%s.apply(%s, %s)\n' % (\
								indent,
								parts[0].strip(),
								parent_method,
								parent_args[0],
								to_star_args(parent_args[1:]))
						else:
							line = '%s%s.prototype.%s.call(%s' % (\
								indent, 
								parts[0].strip(),
								parent_method,
								set_args(parent_args)[1:-2]+'\n')
					elif line.find('(') < line.find('*') < line.find(')') \
					and re.match(r'^[^\'"]*(([\'"])[^\'"]*\2)*[^\'"]*[,(]\s*\*.*[A-Za-z$_][A-Za-z0-9$_]*\s*\)', line):
						# normal line with args, we need to check if it has *args
						args = get_args(line, False, False)
						if args and args[-1][0] == '*':
							function = line.split('(')[0]
							if function.find('.') != -1:
								obj = function.rsplit('.', 1)[0].split('[')[0]
							else:
								obj = 'this'
							# handle *args
							line = '%s.apply(%s, %s)\n' % (\
								function,
								obj,
								to_star_args(args[0:]))
					line = line.replace('self.', 'this.')
					line = add_new_keyword(line)
					write_buffer(line)
			elif line[:6] != 'class ':
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
					and re.match(r'^[^\'"]*(([\'"])[^\'"]*\2)*[^\'"]*[,(]\s*\*.*[A-Za-z$_][A-Za-z0-9$_]*\s*\)', line):
						args = to_star_args(get_args(line, False, False))
						if function.find('.') != -1:
							obj = function.rsplit('.', 1)[0].split('[')[0]
						else:
							obj = 'this'
						line = re.sub('\(.*\)' , '.apply(%s, %s)' % (obj, args), line)
					
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

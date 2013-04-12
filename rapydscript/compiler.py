#!/usr/bin/env python

import sys, re, os
import string
from grammar import Grammar, Translator, compile
from codecheck import verify_code
from exceptions import update_exception_indent_data, process_exception_line

# treat native JavaScript objects like classes
class_list = ['Image', 'RegExp', 'Error', 'Object', 'String', 'Array', 'Number', 'Function', 'Date', 'Boolean',
				'ArrayBuffer', 'DataView', 'Float32Array', 'Float64Array', 'Int16Array', 'Int32Array', 'Int8Array',
				'Uint16Array', 'Uint32Array', 'Uint8Array', 'Uint8ClampedArray']
global_object_list = {}
global_buffer = ''

def find_all(line, sub, remove_escaped=False):
	"""
	Returns array of all occurences of sub in a line
	"""
	matches = [match.start() for match in re.finditer(re.escape(sub), line)]
	if remove_escaped:
		for index in matches[:]:
			if line[index-1] == '\\':
				matches.remove(index)
	return matches

def pop_while_inside(arr1, arr2, pop_arr2=True):
	"""
	Keep popping from arr1 while its values are less than arr2[1].
	arr2[0] and arr2[1] will also be popped
	"""
	count = 0
	if pop_arr2:
		arr2.pop(0)
	try:
		while arr1.pop(0) < arr2[0]:
			count += 1
	finally:
		if pop_arr2:
			arr2.pop(0)
	return count

def terminates_inside_comment(line):
	"""
	Returns True if string terminates before comment ("|') closes
	"""
	single = find_all(line, "'", True)
	double = find_all(line, '"', True)
	
	try:
		while single[0] and double[0]:
			if min(single[0], double[0]) == single[0]:
				pop_while_inside(double, single)
			else:
				pop_while_inside(single, double)
	except IndexError:
		if (len(single) + len(double))%2:
			return True
		else:
			return False

class State:
	def __init__(self, file_name, debug):
	
		# basic info about current state
		self.debug = debug			# identify whether the output should include extra annotation for debugging purposes
		self.indent = ''			# current indent offset (currently only used by class)
		self.incomment = False		# identifies if we're currently in multi-line string (used to prevent parsing strings)
		self.docstring = False		# true if multi-line string is not assigned to anything (used as a docstring)
		self.comment_type = None	# if in string, identifies the quote type that started the string
		self.comment_buffer = ''	# temporarily stores content of multiline comments
		
		# current class info
		self.inclass = False		# True if we're currently inside a class definition
		self.initdef = False		# True if code defines __init__ method explicitly
		self.class_name = None		# if in class, defines the class name
		self.parent = None			# if in class, defines the class we inherited from
		self.methods = []			# if in class, identifies member methods of this class that have been processed so far
		self.post_init_dump = ''	# code to write into the buffer after __init__ definition
		
		# current function info
		self.arg_dump = []			# contains code used to set optional arguments in case they're not passed in
		self.function_indent = None	# indentation level of this particular function
		self.post_function = []		# store 'to-do' logic to perform after function definition
        
		# current exception info
		self.exception_stack = []	# current exception stack (used when processing try/except blocks)
		self.comment_dump = []		# if in a exception block, save the comments for later processing/indentation fixing
		
		# current file statistics
		self.basic_indent = ''		# basic indent marker used by the file (a sequence of whitespace characters)
		self.file_buffer = ''		# parsed portion of the current file (after RapydScript logic, but before PyvaScript)
		self.file_name = file_name	# name of currently parsed file
		self.line_num = 0			# line number we're currently on inside the file we're currently parsing
		self.line_content = ''		# line content of the current line
		self.multiline_start_num = -1	# line number where multiline content started, used with lines stitched via \
		self.multiline_content = ''		# content of entire multi-line block after stitching \-lines together
	
	def get_indent(self, line):
		indent = line[:len(line)-len(line.lstrip())].rstrip('\n') # in case of empty line, remove \n
		if not self.basic_indent:
			self.basic_indent = indent
		return indent
	
	def get_args(self, line, isclass=True, isdef=True):
		# get arguments and sets arg_dump as needed (for handling optional arguments)
		args = line.split('(', 1)[1].rsplit(')', 1)[0].split(',')
		for i in range(len(args)):
			args[i] = args[i].strip()
			if isdef and args[i].find('=') != -1:
				assignment = args[i].split('=') 
				value = convert_keyword_to_js(assignment[1].strip())
				args[i] = assignment[0].strip()
				self.arg_dump.append('JS(\'if (typeof %s === "undefined") {%s = %s};\')\n' % (args[i], args[i], value))
	
		# remove "fake" arguments
		args = filter(None, args)
	
		if isclass:
			args.pop(0)
	
		return args
	
	def parse_fun(self, line, isclass=True):
		method_name = line.split('(')[0]
		method_args = self.get_args(line, isclass)
		return method_name, method_args
	
	def get_arg_dump(self, line):
		"""
		Retrieves optional arguments for this function
		"""
		output = ''
		if self.arg_dump:
			indent = self.get_indent(line)
			for var in self.arg_dump:
				output += indent+var #dump optional variable declarations
			self.arg_dump = []
		return output
	
	def reset(self, full_reset=False):
		if not full_reset:
			indent = self.indent
			basic_indent = self.basic_indent
			line_num = self.line_num
			file_buffer = self.file_buffer
		self.__init__(self.file_name, self.debug)
		if not full_reset:
			self.indent = indent
			self.basic_indent = basic_indent
			self.line_num = line_num
			self.file_buffer = file_buffer
	
	def write_buffer(self, input):
		self.file_buffer += input
	
	def update_incomment_state(self, line):
		"""
		Toggles the current program state to 'incomment' if it encounters 
		unmatched multi-line quote on the line (triple-" or triple-'). This
		allows RapydScript preprocessor to ignore doc-strings and multi-line
		strings, which could otherwise get mutilated or trigger a false error.
		"""
		
		# helper method only relevant to this function
		def check_for_valid_multiline_quote(comment_type, triggering_list, other_list, sub):
			"""
			Checks if this line starts a valid comment, and updates state accordingly
			"""
	
			triggering_list.pop(0)
			if not terminates_inside_comment(sub):
				# valid quote (doesn't occur inside another quote), enter comment mode
				self.comment_type = comment_type
				self.incomment = not self.incomment
	
		# begin function
		single = find_all(line, "'''")
		double = find_all(line, '"""')
		sub_list = [y for z in [x.split('"""') for x in line.split("'''")] for y in z]
		# in 99% of the cases, we'll skip directly to the end of the loop, there
		# will only be one quote in the line, but we should check for all special
		# cases anyway
		while single and double:
			index = min(single[0], double[0])
			sub = sub_list.pop(0)
			if index == single[0]:
				n = pop_while_inside(double, single, False)
				check_for_valid_multiline_quote("'''", single, double, sub)
			else:
				n = pop_while_inside(single, double, False)
				check_for_valid_multiline_quote('"""', double, single, sub)
			sub_list = sub_list[n:]
		sub = sub_list.pop(0)
		while single:
			check_for_valid_multiline_quote("'''", single, double, sub)
		while double:
			check_for_valid_multiline_quote('"""', double, single, sub)
		if self.incomment and line.lstrip()[:3] in ('"""', "'''"):
			self.docstring = True

imported_files = []
def import_module(line, state):
	tokens = line.split()
	if len(tokens) == 2 and tokens[0] == 'import':
		import_file = tokens[1]
	elif len(tokens) == 4 and tokens[0] == 'from' and tokens[2] == 'import':
		import_file = tokens[3]
	else:
		raise ImportError("Invalid import statement: %s" % line.strip())
	
	if import_file not in imported_files:
		try:
			parse_file(import_file.replace('.', '/') +'.pyj', state.debug)
		except IOError:
			# couldn't find the file in local directory, check RapydScript lib directory
			cur_dir = os.getcwd()
			try:
				# we have to rely on __file__, because cwd could be different if invoked by another script
				os.chdir(os.path.dirname(__file__))
				parse_file(import_file.replace('.', '/') +'.pyj', state.debug)
			except IOError:
				raise ImportError("Can't import %s, module doesn't exist" % import_file)
			finally:
				os.chdir(cur_dir)
		imported_files.append(import_file)
		
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

js_map = {'None' : 'null', 'True' : 'true', 'False' : 'false'}
def convert_keyword_to_js(value):
	if value in js_map.keys():
		return js_map[value]
	else:
		return value

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
	"""
	This logic allows some non-Pythonic syntax in favor of JavaScript-like function usage (chaining, 
	and calling anonymous function without assigning it)
	"""
	return 'JS("<<_rapydscript_bind_>>%s;")\n' % line.rstrip().replace('"', '\\"')

def bind_chained_calls(source):
	"""
	This logic finalizes the above logic after PyvaScript has run
	"""
	source = re.sub(r';\s*\n*\s*<<_rapydscript_bind_>>', '', source, re.MULTILINE) # handle semi-colon binding
	return re.sub(r'}\s*\n*\s*<<_rapydscript_bind_>>', '}', source, re.MULTILINE) # handle block binding

def print_exception_comments(state, exception_info, added_indent, test_equal=False):

	source_indent = exception_info['source_indent']				
	remove_inds = []
	for j in xrange(len(state.comment_dump)):
		comment = state.comment_dump[j]
		comment_indent = state.get_indent(comment)
		comment_indent_size = len(comment_indent)
		if (comment_indent_size > source_indent) or \
				(test_equal and (comment_indent_size == source_indent)):
			state.write_buffer(added_indent)
			state.write_buffer(comment.lstrip())
			remove_inds.append(j)
	for remove_ind in reversed(remove_inds):
		del state.comment_dump[remove_ind]

def make_exception_updates(line, lstrip_line, state):

	if len(state.exception_stack) > 0:
		exception_info = state.exception_stack[-1]
	else:
		exception_info = None

	# Get information about the current indent (account for class's)
	indent = state.get_indent(line)
	indent_size = len(indent)
	if state.inclass:
		indent_size -= len(state.indent)


	# Update any indent information
	if exception_info and 'if_block_indent' not in exception_info:
		exception_info = update_exception_indent_data(exception_info, indent_size, line[0], state.exception_stack)


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
				state.write_buffer('%s:\n' % write_str)
			elif not exception_info['first_exception']:
				# printing el+se (%sse) to the output
				state.write_buffer('%sse:\n' % write_str)

			# set any variables that the user has specified
			if exception_info and exception_info['var_name']:
				state.write_buffer('%s%s = %s\n'% \
				(exception_info['code_indent'], exception_info['var_name'], exception_info['exception_var']))

	# Print any exceptions before the indent
	if state.exception_stack:
		added_indent = exception_info['code_indent']

		print_exception_comments(state, exception_info, added_indent)


	# Print and remove exited exceptions
	# Test whitespace to see if we got ouside an except block
	is_except_line = lstrip_line.startswith('except')
	for i in xrange(len(state.exception_stack)-1, -1, -1):
		# Exited an except block if:
		# - current indent < exception indent
		# - current indent == exception indent AND isn't catching another exception in a try block
		if (indent_size < state.exception_stack[i]['source_indent']) or \
				(indent_size == state.exception_stack[i]['source_indent'] and not is_except_line):
			
			exited_exception = state.exception_stack.pop()
			if exited_exception['exceptions']:
				# if we were catching specific exceptions, throw any exceptions that were not caught
				state.write_buffer('%selse:\n%sraise %s\n' % \
							(exited_exception['if_block_indent'],
							exited_exception['code_indent'],
							exited_exception['exception_var']))
				#print all comments
				for comment in state.comment_dump:
					state.write_buffer(comment)
				state.comment_dump = []
			else:
				if state.exception_stack:
					added_indent = state.exception_stack[-1]['code_indent']
				elif state.inclass:
					added_indent = state.indent
				else:
					added_indent = ''
				
				print_exception_comments(state, exited_exception, added_indent,
										test_equal=True)
		else:
			# did not exit the except block, so stop trying
			break
	
	# Update the exception information and update the line with any neccesary added indents
	line, state.exception_stack = process_exception_line(line, indent, indent_size, is_except_line,
										state.exception_stack, exception_info)

	lstrip_line = line.lstrip()
	return line, lstrip_line

def parse_file(file_name, debug=False):
	# parse a single file into global namespace
	global global_buffer
	state = State(file_name, debug)
	
	# Each line goes through the following 5 stages. The order is important, we don't want to 
	# start interpreting the line until we know all of its contents.
	
	# stage 0: standardize input and check if any processing is required
	# stage 1: stitching multi-line logic and multi-line strings together (unifying lines)
	# stage 2: split lines at semi-colons and inlined functions (separating lines)
	# stage 3: strip empty and doc-string lines, perform any 'to-do' logic inferred from previous line
	# stage 4: processing/interpreting the line
	
	# stage 2:
	# split lines at semi-colons and inlined functions (separating lines)
	# also triggers stage 3 when done
	def stage2(line, state):
		lstrip_line = line.lstrip()
		# separate inline function definitions ( def(x): return x*x ) into proper functions
		pair = None
		if line.find('def') and re.search(r'\bdef\(', line):
			pair = line.split('):')
			stage3(pair[0]+'):\n', state)
			line = state.get_indent(pair[0])+state.basic_indent+pair[1].lstrip()
		# separate lines at semi-colons:
		sub_lines = line.rstrip().split(';')
		final_lines = []
		indent = state.get_indent(line)
		inside_string = False
		for sub_line in sub_lines:
			if inside_string:
				# continuing to stitch a string from before
				final_lines[-1] += ';' + sub_line
				if not terminates_inside_comment(final_lines[-1]):
					inside_string = False
			elif terminates_inside_comment(sub_line):
				# this is a string, stitch it back together
				if inside_string:
					final_lines[-1] += ';' + sub_line
				else:
					final_lines.append(sub_line)
				inside_string = True
			else:
				# this is a sub-line, apply same indent as the main line
				lstrip_sub_line = sub_line.lstrip()
				if lstrip_sub_line:
					final_lines.append(indent + lstrip_sub_line)
		
		# stages 3+ are performed inside stage3() logic, this is to allow function
		# shorthands: 
		#	def(a, b): return a+b
		#	def(a, b): a += b; return a
		
		# send 2nd group to stage 3
		for line_chunk in final_lines:
			stage3(line_chunk + '\n', state)
		
		# send the rest back to beginning of stage 2
		# this will occur in case of multiple inline functions:
		# func1(def(a, b): return a+b;, def(c, d): return c*d)
		if pair and len(pair) > 2:
			stage2('):'.join(pair[2:]), state)
	
	# stages 3+4:
	# finalizes line processing
	# stage 3: strip empty and doc-string lines, perform any 'to-do' logic inferred from previous line
	# stage 4: processing/interpreting the line
	def stage3(line, state):
		global global_buffer
	
		# we can't simply pass in old lstrip_line since the line could have been split
		lstrip_line = line.lstrip()
	
		# stage 3:
		# add an extra indent if needed, perform post-function-definition logic
		is_nonempty_line = len(lstrip_line) > 1 or \
			len(lstrip_line) == 1 and lstrip_line[0] != '\n'
		if state.function_indent >= state.get_indent(line):
			for post_line in state.post_function:
				state.write_buffer(post_line)
			state.post_function = []
			state.function_indent = None
		
		# Convert an except to the format accepted by PyvaScript
		is_except_line = False
		if lstrip_line.startswith('except') or \
				lstrip_line.startswith('finally'):
			is_except_line = True
		
		if is_except_line or (state.comment_dump or 
							  (state.exception_stack and is_nonempty_line)):
			line, lstrip_line = make_exception_updates(line, lstrip_line, state)
		
		# stage 4:
		if line.find('def') != -1 and line.find('def') < line.find(' and ') < line.find(':') and \
				not lstrip_line.startswith('.while') and \
				re.match('^(\s*)(def\s*\(.*\))\s+and\s+([A-Za-z_$][A-Za-z0-9_$]*\(.*\)):$', line):
			# handle declaration and call at the same time
			groups = re.match('^(\s*)(def\s*\(.*\))\s+and\s+([A-Za-z_$][A-Za-z0-9_$]*\(.*\)):$', line).groups()
			line = groups[0] + groups[1] + ':\n'
			indentation = groups[0]
			if state.inclass:
				indentation = indentation[len(state.indent):] # dedent
			state.post_function.append('%s%s\n' % (indentation, wrap_chained_call('.%s' % groups[2])))
			function_indent = groups[0]
		if line[:5] == 'from ' or line[:7] == 'import ':
			if state.debug:
				global_buffer += '//Encountered import statement in %s: %s\n' % (file_name, line)
			import_module(line, state)
			return
		if line[:6] == 'class ':
			# class definition
			# this is where we do our 'magic', creating 'bad' Python that PyvaScript naively translates
			# into good JavaScript
			
			# if we were already processing another class, finalize it now
			if state.post_init_dump:
				state.write_buffer(state.post_init_dump)
				state.post_init_dump = ''
			
			state.reset()
			state.inclass = True
			class_data = line[6:].split('(')
			if len(class_data) == 1: #no inheritance
				state.class_name = class_data[0][:-2] #remove the colon and newline from the end
			else:
				state.class_name = class_data[0]
				state.parent = class_data[1][:-3] #assume single inheritance, remove '):'
				new_prefix = ''
				# TEMP: temporarily set to always-on due to current class limitations
				#if state.parent in class_list:
				#	new_prefix = 'new '
				new_prefix = 'new '
				state.post_init_dump += '%s.prototype = %s%s()\n' % (state.class_name, new_prefix, state.parent)
			class_list.append(state.class_name)
			state.indent = state.basic_indent
		elif line[0] not in (' ', '\t', '\n'):
			#line starts with a non-space character
			if state.post_init_dump:
				state.write_buffer(state.post_init_dump)
				state.post_init_dump = ''
			state.inclass = False
			
		# convert list comprehensions
		# don't bother performing expensive regex unless the line actually has 'for' keyword in it
		if line.find(' for ') != -1:
			line = convert_list_comprehension(line)

		# handle JavaScript-like chaining
		if state.file_buffer and state.file_buffer[-1] == '\n' and \
				lstrip_line and not lstrip_line.startswith('.while') and lstrip_line[0] == '.':
			if state.inclass:
				line = line[len(state.indent):] # dedent
			state.write_buffer(line.split('.')[0] + wrap_chained_call(lstrip_line))
			return

		# process the code as if it's part of a class
		# Again, we do more 'magic' here so that we can call parent (and non-parent, removing most of
		# the need for multiple inheritance) methods.
		if state.inclass and line[:6] != 'class ':
			if line.lstrip()[:12] == 'def __init__':
				# constructor definition
				state.initdef = True
				if state.parent is not None:
					state.post_init_dump += '%s.prototype.constructor = %s\n' % (state.class_name, state.class_name)
				init_args = state.get_args(line)
				state.write_buffer('def %s%s' % (state.class_name, set_args(init_args)))
			elif line[:len(state.indent)+4] == state.indent + 'def ':
				# method definition
				if not state.initdef:
					#assume that __init__ will be the first method declared, if it is declared
					if state.parent is not None:
						state.post_init_dump += '%s.prototype.constructor = %s\n' % (state.class_name, state.class_name)
						inherited = '%s.prototype.constructor.call(this);' % state.parent
					else:
						inherited = ''
					state.write_buffer('JS(\'%s = function() {%s};\')\n' % (state.class_name, inherited))
					state.initdef = True
				if state.post_init_dump:
					state.write_buffer(state.post_init_dump)
					state.post_init_dump = ''
				method_name, method_args = state.parse_fun(lstrip_line[4:])
				
				# handle *args for function declaration
				post_declaration = []
				if method_args and method_args[-1][0] == '*':
					count = 0
					for arg in method_args[:-1]:
						post_declaration.append('%s = arguments[%s]' % (arg, count))
						count += 1
					post_declaration.append('%s = [].slice.call(arguments, %s)' % (method_args[-1][1:], count))
					method_args = ''
				
				state.write_buffer('%s.prototype.%s = def%s' % (state.class_name, method_name, set_args(method_args)))
				
				# finalize *args logic, if any
				for post_line in post_declaration:
					state.write_buffer(state.get_indent(line) + post_line + '\n')
			elif line.find('def') and re.search(r'\bdef\b', line):
				# normal or anonymous function definition that just happens to be inside a class
				line = line[len(state.indent):] # dedent by 1 because we're inside a class
				fun_def = re.split(r'\bdef\b', line)
				fun_name, fun_args = state.parse_fun(fun_def[1], False)
				
				# handle *args for function declaration
				post_declaration = []
				if fun_args and fun_args[-1][0] == '*':
					count = 0
					for arg in fun_args[:-1]:
						post_declaration.append('%s = arguments[%s]' % (arg, count))
						count += 1
					post_declaration.append('%s = [].slice.call(arguments, %s)' % (fun_args[-1][1:], count))
					fun_args = ''
					
				state.write_buffer(fun_def[0]+'def%s%s' % (fun_name, set_args(fun_args)))
				
				# finalize *args logic, if any
				for post_line in post_declaration:
					state.write_buffer(state.get_indent(line) + state.basic_indent + post_line + '\n')
			else:
				# regular line
				line = line[len(state.indent):] # dedent by 1 because we're inside a class
				state.write_buffer(state.get_arg_dump(line))
				
				if line.find('.__init__') != -1:
					line = line.replace('.__init__(', '.prototype.constructor.call(')
				elif invokes_method_from_another_class(line):
					# method call of another class
					indent = state.get_indent(line)
					parts = line.split('.')
					parent_method = parts[1].split('(')[0]
					parent_args = state.get_args(line, False)
					
					if parent_args[-1][0] == '*':
						# handle *args
						line = '%s%s.prototype.%s.apply(%s, %s)' % (\
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
							set_args(parent_args)[1:-2])
					if state.line_content.rstrip()[-1] == ':':
						line += ':'
					line += '\n'
				elif line.find('(') < line.find('*') < line.find(')') \
				and re.match(r'^[^\'"]*(([\'"])[^\'"]*\2)*[^\'"]*[,(]\s*\*.*[A-Za-z$_][A-Za-z0-9$_]*\s*\)', line):
					# normal call with args, we need to check if it has *args
					args = state.get_args(line, False, False)
					if args and args[-1][0] == '*':
						function = line.split('(')[0]
						if function.find('.') != -1:
							obj = function.rsplit('.', 1)[0].split('[')[0]
						else:
							obj = 'this'
						# handle *args
						line = '%s.apply(%s, %s)' % (\
							function,
							obj,
							to_star_args(args[0:]))
					if state.line_content.rstrip()[-1] == ':':
						line += ':'
					line += '\n'
				line = line.replace('self.', 'this.')
				line = add_new_keyword(line)
				state.write_buffer(line)
		elif line[:6] != 'class ':
			line = add_new_keyword(line)
			if line.find('def') != -1 and re.search(r'\bdef\b', line):
				# find() filters out the first 90% of the cases, and the expensive regex
				# is only performed on the last few cases to keep the compiler fast
				
				# function definition, has to handle normal functions as well as anonymous ones
				fun_def = re.split(r'\bdef\b', line)
				fun_name, fun_args = state.parse_fun(fun_def[1], False)
				
				# handle *args for function declaration
				post_declaration = []
				if fun_args and fun_args[-1][0] == '*':
					count = 0
					for arg in fun_args[:-1]:
						post_declaration.append('%s = arguments[%s]' % (arg, count))
						count += 1
					post_declaration.append('%s = [].slice.call(arguments, %s)' % (fun_args[-1][1:], count))
					fun_args = ''
					
				state.write_buffer(fun_def[0]+'def%s%s' % (fun_name, set_args(fun_args)))
				
				# finalize *args logic, if any
				for post_line in post_declaration:
					state.write_buffer(state.get_indent(line) + state.basic_indent + post_line + '\n')
			else:
				# regular line
				
				# the first check is a quick naive check, making sure that there is a * char
				# between parentheses
				# the second check is a regex designed to filter out the remaining 1% of false
				# positives, this check is much smarter, checking that there is a ', *word)'
				# pattern preceded by even number of quotes (meaning it's unquoted)
				if line.find('(') < line.find('*') < line.find(')') \
				and re.match(r'^[^\'"]*(([\'"])[^\'"]*\2)*[^\'"]*[,(]\s*\*.*[A-Za-z$_][A-Za-z0-9$_]*\s*\)', line):
					args = to_star_args(state.get_args(line, False, False))
					if function.find('.') != -1:
						obj = function.rsplit('.', 1)[0].split('[')[0]
					else:
						obj = 'this'
					line = re.sub('\(.*\)' , '.apply(%s, %s)' % (obj, args), line)
				
				state.write_buffer(state.get_arg_dump(line))
				state.write_buffer(line)

	# begin parsing file
	with open(file_name, 'r') as input:
		# check for easy to spot errors/quirks we require
		if not verify_code(file_name, input, global_object_list):
			sys.exit()

		# find correct indent first, to avoid special cases if 'magic'
		# needs to be isnerted into output before indent is found
		input.seek(0)
		for line in input:
			line = line.replace('\r','')
			if len(state.get_indent(line)): break

		print len(state.get_indent(line)), repr(line)
		input.seek(0)
		if state.debug:
			decor = '//////////////////////////////////////////////////////////////////////'
			top_strip = 'JS("""\n\n%s\n%s""")' % (decor, decor)
			btm_strip = 'JS("""%s\n%s\n""")' % (decor, decor)
			state.write_buffer('\n%s\n#Parsing File: %s\n%s\n' % (top_strip, file_name, btm_strip))
		for line in input:
			state.line_num += 1
			state.line_content = line

			# stages 0+1 are performed in the loop itself, since they're not recursive like later stages
			
			# stage 0: standardize input and check if any processing is required
			# stage 1: stitching multi-line logic and multi-line strings together (unifying lines)
			
			# stage 0:
			# standardize input and check if any processing is required
			# convert DOS to UNIX format (handles files written in Windows)
			line = line.replace('\r','')
			# log original line to output if in debug mode
			if state.debug:
				state.write_buffer('#%d:\t%s' % (state.line_num, line))
			lstrip_line = line.lstrip()
			# strip comments (we'll strip them later anyway in normal mode, and they're redundant in debug)
			if lstrip_line and lstrip_line[0] == '#':
				continue
			# check if pre-processing is required
			previously_comment = state.incomment
			state.update_incomment_state(line)
			if state.incomment or previously_comment:
				if state.inclass and len(line) > len(lstrip_line):
					line = line[len(state.basic_indent):]
				if not state.docstring:
					if not state.exception_stack:
						state.comment_buffer += line
					else:
						state.comment_dump.append(line)
				continue
			elif not state.incomment and state.comment_buffer:
				state.write_buffer(state.comment_buffer)
				state.comment_buffer = ''
			state.docstring = False
			
			# stage 1:
			# stitch together lines ending with \
			if not state.multiline_content:
				state.multiline_start_num = -1
			else:
				# continuing, strip indent
				line = lstrip_line
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
				
			stage2(line, state)
	
	# end of file, write any unwritten code to buffer
	if state.post_init_dump:
		state.write_buffer(state.post_init_dump)
		state.post_init_dump = ''

	print state.file_buffer
	try:
		global_buffer += finalize_source(state.file_buffer, state.debug)
		if state.debug:
			global_buffer += '//Finished parsing %s\n' % file_name
	except:
		print "Parse Error in %s:\n" % file_name
		raise
	return global_buffer

def finalize_source(source, debug):
	g = Grammar.parse(source)

	output = Translator.parse(g, debug_flag=debug)
	#PyvaScript seems to be buggy with self replacement sometimes, let's fix that
	output = re.sub(r'\bself\b', 'this', output)
	output = bind_chained_calls(output)
	return output

import re
import string


def warn(file_name, line_num, message, error_type = 'ERROR'):
	print('*** %s: %s, line %d: %s ***' % (error_type, file_name, line_num, message))

def warn2(warning, error_type = 'ERROR'):
	print('*** %s: %s' % (error_type, warning))

	
def verify_code(f, source, global_object_list, auto_correct=False):
	success = True

	# check for consistent whitespace
	indent = None
	line_num = 0
	pattern_defined = False
	for line in source:
		line_num += 1
		if indent is None and line[0] == ' ' or line[0] == '\t':
			indent = line[0] #remember spacing preference
			if indent[0] == ' ':
				bad_pattern = r'^\s*\t'
			else:
				bad_pattern = r'^\s* '
			pattern_defined = True
		if pattern_defined and re.match(bad_pattern, line):
			warn(f, line_num, 'File contains mixed indentation, please change all tabs to spaces or spaces to tabs.')
			success = False
	
	# check for global object name collision (only def and class objects are checked)
	line_num = 0
	source.seek(0)
	for line in source:
		line_num += 1
		global_objects = []
		if line[0:4] == 'def ' or line[0:6] == 'class ':
			# this handles functions and classes
			tokens = line.split()
			global_objects.append(tokens[1].split('(')[0].replace(':','').strip())
		elif line[0] in string.letters and line[0:3] != 'if ' and line.count('=') > 0:
			# this handles the following:
			#	a = <value>
			#	b = a = <value>
			objects = line.split('=')
			for item in objects[:-1]:
				global_objects.append(item.strip())
		
		if global_objects:
			for global_object in global_objects:
				if global_object in global_object_list.keys():
					#warn(f, line_num, 'Global object "%s" already defined earlier, possible name collision.' % global_object)
					warn2('Global object "%s" defined in %s, line %s conflicts with earlier definition in %s, line %s' % (global_object, f, line_num, global_object_list[global_object][0], global_object_list[global_object][1]))
					success = False
				else:
					global_object_list[global_object] = (f, line_num)
	
	# check for compatible comments
	line_num = 0
	source.seek(0)
	for line in source:
		line_num += 1
		if re.search('(\S+\s*("""|\'\'\')\s*\S*|\S*\s*("""|\'\'\')\s*\S+)', line):
			warn(f, line_num, 'Docstrings should have the quote on separate line, the compiler gets confused otherwise.')
			success = False
	
	# check for compatible comment spacing
	line_num = 0
	source.seek(0)
	post_comment_block = False
	for line in source:
		line_num += 1
		if re.search('("""|\'\'\')', line):
			post_comment_block = True
		elif post_comment_block and not len(line.strip()):
			warn(f, line_num, 'The line directly after a docstring must not be a blank line.')
			success = False
		else:
			post_comment_block = False
		
	# check for compatible if statements
	line_num = 0
	source.seek(0)
	for line in source:
		line_num += 1
		if re.match('^if\(', line.lstrip()):
			warn(f, line_num, 'Compiler gets confused unless there is a space between if statement and the paranthesis.')
			success = False
	
	# check for implicit 0 before period
	line_num = 0
	source.seek(0)
	for line in source:
		line_num += 1
		if re.search('[^0-9]\.[0-9]', line):
			warn(f, line_num, 'Implicit 0 for the interger portion of a decimal, compiler doesn\'t support those.')
			success = False
	
	# check for compatible math functions
	bad_math = ['max(', 'min(', 'sqrt(', 'abs(', 'acos(', 'asin(', 'atan(', \
	'atan2(', 'log(', 'random(', 'round(', 'pow(', 'cos(', 'sin(', 'tan(', 'ceil(', 'floor(']
	line_num = 0
	source.seek(0)
	for line in source:
		line_num += 1
		for function in bad_math:
			pos = line.find(function)
			if pos != -1 and (line[pos-5:pos] == 'math.' or pos == 0):
				warn(f, line_num, 'Possible incorrect use of Math method %s), make sure to use JavaScript version' % function)
				success = False
	return success

				
				
def make_strict(source):
	#replace == and != with stricter === and !==
	for line in source:
		line = re.sub('(?<=[!=])=(?!=)', '==', line)
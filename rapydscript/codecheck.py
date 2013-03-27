import re
import string
from rapydscript.exceptions import EXCEPT_REGEX


def warn(file_name, line_num, message, error_type = 'ERROR'):
	print('*** %s: %s, line %d: %s ***' % (error_type, file_name, line_num, message))

def warn2(warning, error_type = 'ERROR'):
	print('*** %s: %s' % (error_type, warning))

	
def verify_code(f, source, global_object_list, auto_correct=False):
	success = True

	indent = None
	line_num = 0
	pattern_defined = False
	post_comment_block = False
	bad_math = ['max(', 'min(', 'sqrt(', 'abs(', 'fabs(', 'acos(', 'asin(', 'atan(', \
	'atan2(', 'log(', 'random(', 'round(', 'pow(', 'cos(', 'sin(', 'tan(', 'ceil(', 'floor(']
	for line in source:
		line_num += 1
		lstrip_line = line.lstrip()
		
		# check for consistent whitespace
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
		global_objects = []
		if line[0:4] == 'def ' or line[0:6] == 'class ':
			# this handles functions and classes
			tokens = line.split()
			global_objects.append(tokens[1].split('(')[0].replace(':','').strip())
		elif line[0] in string.letters and line[0:3] != 'if ' and line.count('=') > 0:
			# this handles the following:
			#	a = <value>
			#	b = a = <value>
			#	a = b == c
			#	a = [i+=1 for i in b if i%2==0]
			# we'll strip everything before first quote since we know this is not valid code:
			#	a = "string" = b = <value>
			assignment_chunk = line.split("'")[0].split('"')[0]
			objects = re.findall('([A-Za-z_$][A-Za-z0-9_$]*)[^=><!]*=[^=]', assignment_chunk)
			for item in objects[:-1]:
				global_objects.append(item.strip())
		if global_objects:
			for global_object in global_objects:
				if global_object in global_object_list.keys():
					warn2('Global object "%s" defined in %s, line %s conflicts with earlier definition in %s, line %s' % (global_object, f, line_num, global_object_list[global_object][0], global_object_list[global_object][1]))
					success = False
				else:
					global_object_list[global_object] = (f, line_num)
		
		# check for implicit 0 before period
		if re.search('[^0-9]\.[0-9]', line):
			warn(f, line_num, 'Implicit 0 for the interger portion of a decimal, compiler doesn\'t support those.')
			success = False

		# check for parsable except lines
		if lstrip_line.startswith('except'):
			if not EXCEPT_REGEX.match(line):
				warn(f, line_num, 'Cannot parse Except Line')
				success = False

		# check for compatible math functions
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

import re

mand_space = r'[\s\t]+'
opt_space = r'[\s\t]*'
var_name = r'[a-zA-Z_][a-zA-Z0-9_]*'

RAPD_ERR = '_$rapyd$_Exception'

EXCEPT_PATTERN = r'%sexcept(%s(?:(?:%s)%s,%s)*(?:%s))?(?:%sas%s(%s))?%s:%s$' % \
        (opt_space, mand_space, var_name, opt_space, opt_space, var_name,
         mand_space, mand_space, var_name, opt_space, opt_space)
        
EXCEPT_REGEX = re.compile(EXCEPT_PATTERN)


def update_exception_indent_data(exception_info, indent_size, indent_char, exception_info_list):
    #The size of the indent under the except block
    sub_indent_size = indent_size - exception_info['source_indent']

    #Generate a string for the except block & the indent under the except block
    sub_indent_str = indent_char * sub_indent_size

    if len(exception_info_list) > 1:
        except_indent_str = exception_info_list[-2]['code_indent']
        added_indent = exception_info_list[-2]['added_indent']
    else:
        except_indent_str = indent_char * exception_info['source_indent']
        added_indent = ''

    #Save some indent strings for writing to the buffer later on
    exception_info['if_block_indent'] = except_indent_str + sub_indent_str
    if exception_info['exceptions']:
        exception_info['added_indent'] = added_indent + sub_indent_str
        add_str = sub_indent_str
    else:
        #No if statements, just need code & added indent
        exception_info['added_indent'] = added_indent
        add_str = ''
    exception_info['code_indent'] = except_indent_str + sub_indent_str + add_str

    return exception_info


def parse_exception_line(line):
    """
    recognize:
    - except:
    - except ExceptionName1, ExceptionName2:
    - except as var_name:
    - except ExceptionName1, ExceptionName2 as var_name:
    """
    parsed_exception = EXCEPT_REGEX.match(line).groups()
    #if parsed_exceptions is None or len(parsed_exceptions) != 2:
    #    raise Exception('Cannot parse exception line')
    exception_list = []
    if parsed_exception[0]:
        for exception in parsed_exception[0].split(','):
            exception_list.append(exception.strip())

    # The var name could be None
    var_name = parsed_exception[1]

    return var_name, exception_list


def process_exception_line(line, indent, indent_size, is_except_line,
                           exception_stack, exception_info):

    #See if any indent is required based on the current exception stack
    current_added_indent = ''
    if len(exception_stack) > 0 and exception_stack[-1] and \
            'added_indent' in exception_stack[-1]:
        current_added_indent = exception_stack[-1]['added_indent']


    if is_except_line:
        #Parse the line
        var_name, exception_list = parse_exception_line(line)
        exception_var = '%s' % RAPD_ERR
        
        first_exception = True
        if exception_info:
            #If there is already exception information, then this is only
            # a first exception if it is a nested except (increased indent)
            first_exception = indent_size > exception_info['source_indent']

        if first_exception:
            #Save the indent size only on the first exception in a set
            new_exception = {'source_indent': indent_size,
                             'exception_var': exception_var}
        else:
            #If this is not he first exception, reuse data from the previous
            #exception - this is really just indent information
            new_exception = exception_stack.pop(-1)
        #Always update this information
        new_exception['exceptions'] = exception_list
        new_exception['var_name'] = var_name
        new_exception['first_exception'] = first_exception
        new_exception['printed'] = False #if exceptionn instanceof exception
        exception_stack.append(new_exception)

        if first_exception:
            # If this is the first exception seen in a series of exceptions,
            # the line we pass to the ast parser will be except <exception_var>
            line = indent + 'except %s:\n' % exception_var
        else:
            # If this is no the first exception, essentially blank this line
            # instead it will be if <exception_var> instanceof caught exception
            line = '\n'
    

    if current_added_indent:
        line = current_added_indent + line

    return line, exception_stack


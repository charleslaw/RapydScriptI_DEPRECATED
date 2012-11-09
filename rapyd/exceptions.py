import re

mand_space = r'[\s\t]+'
opt_space = r'[\s\t]*'
var_name = r'[a-zA-Z_][a-zA-Z0-9_]*'

RAPD_ERR = '_$rapyd$_Exception'

EXCEPT_PATTERN = r'%sexcept(%s(?:(?:%s)%s,%s)*(?:%s))?(?:%sas%s(%s))?%s:%s$' % \
        (opt_space, mand_space, var_name, opt_space, opt_space, var_name,
         mand_space, mand_space, var_name, opt_space, opt_space)
        
EXCEPT_REGEX = re.compile(EXCEPT_PATTERN)


def update_exception_indent_data(exception_info, indent_size, indent_char):
    #The size of the indent under the except block
    sub_indent_size = indent_size - exception_info['except_indent']
    
    #Generate a string for the except block & the indent under the except block
    sub_indent_str = indent_char * sub_indent_size
    except_indent_str = indent_char * exception_info['except_indent']

    #Save some indent strings for writing to the buffer later on
    exception_info['if_block_indent'] = except_indent_str + sub_indent_str
    if exception_info['exceptions']:
        exception_info['added_indent'] = sub_indent_str
    else:
        #No if statements, just need code & added indent
        exception_info['added_indent'] = ''
    exception_info['code_indent'] = except_indent_str + sub_indent_str + \
                                    exception_info['added_indent']
    
    return exception_info


def parse_exception_line(line, first_exception):
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


def update_exception_info(line, indent, indent_size, is_except_line,
                          outside_block, state, exception_info):
    if not is_except_line:
        if outside_block:
            #Outside the except block, and did not see an except line, we're
            # done with this exception
            state.exceptions = {}
    else:
        first_exception = False if exception_info else True

        var_name, exception_list = parse_exception_line(line, first_exception)
            
        if first_exception and not exception_list:
            #This special case does not require any further processing
            state.exceptions = {}
        else:
            if first_exception:
                #Save the indent size only on the first exception in a set
                state.exceptions = {'except_indent': indent_size}
            #Always update this information
            state.exceptions['exceptions'] = exception_list
            state.exceptions['var_name'] = var_name
            state.exceptions['first_exception'] = first_exception
            state.exceptions['processed'] = False

        if first_exception:
            if exception_list or var_name is None:
                var_name = RAPD_ERR
            # If this is the first exception seen in a series of exceptions,
            # the line we pass to the ast parser will be except <exception_var>
            line = indent + 'except %s:\n' % var_name
        else:
            # If this is no the first exception, essentially blank this line
            # instead it will be if <exception_var>.name == caught exception
            line = '\n'
            
    return line, state


# Run this from the setup.py directory using either:
# python setup.py test
# python tests/grammartests.py

import unittest
from rapydscript.grammar import compile
from textwrap import dedent

class PyvaTest(unittest.TestCase):
    def check(self, source, result):
        source = '\n'.join(line for line in
                           dedent(compile(dedent(source))).strip().splitlines()
                           if line)
        result = '\n'.join(line for line in dedent(result).strip().splitlines()
                           if line)
        try:
            self.assertEqual(source, result)
        except:
            raise AssertionError('\n%s\n!=\n%s' % (repr(source), repr(result)))


class TestTuplePackingUnpacking(PyvaTest):
    def test_ternary_ifs(self):
        self.check("""
            answer = yes if test == alpha else no
            answer = yes if test == alpha else 'No'
            answer = 'Yes' if test == alpha else 'No'
            answer = yes if test == 'alpha' else 'No'
            answer = yes if 'test' == alpha else 'No'
            answer = yes if 'alpha' == test else 'No'
        """, """
            answer = ((test == alpha) ? yes : no);
            answer = ((test == alpha) ? yes : "No");
            answer = ((test == alpha) ? "Yes" : "No");
            answer = ((test == "alpha") ? yes : "No");
            answer = (("test" == alpha) ? yes : "No");
            answer = (("alpha" == test) ? yes : "No");
        """)


    def test_return_normal_not_packed(self):
        self.check("""
            def():
                return [1, 2, 3]
            """, """
            function() {
              return [1, 2, 3];
            }
            """)
        
    def test_return_pack_normal(self):
        self.check("""
            def():
                return 'a', 2
            """, """
            function() {
              return ["a", 2];
            }
            """)
        self.check("""
            def():
                return a, b2
            """, """
            function() {
              return [a, b2];
            }
            """)
        self.check("""
            def():
                return a
            """, """
            function() {
              return a;
            }
            """)
        self.check("""
            def():
                return a,
            """, """
            function() {
              return [a];
            }
            """)

    def test_return_pack_tuples(self):
        self.check("""
            def():
                return 1, (2, 3), 4,(5,6)
            """, """
            function() {
              return [1, [2, 3], 4, [5, 6]];
            }
            """)

    def test_return_pack_lists(self):
        self.check("""
            def():
                return 1, [2, 3], 4,[5,6]
            """, """
            function() {
              return [1, [2, 3], 4, [5, 6]];
            }
            """)

    def test_return_pack_strings_with_commas(self):
        self.check("""
            def():
                return 'a', 'hello, test',
            """, """
            function() {
              return ["a", "hello, test"];
            }
            """)

    def test_return_pack_function_call(self):
        self.check("""
            def():
                return 'a',2,callme('b', 2,c),'last, one'
            """, """
            function() {
              return ["a", 2, callme("b", 2, c), "last, one"];
            }
            """)

    def test_assigment_left_two(self):
        self.check("""
            vara, varb = callme('var', c)
            """, """
            _$rapyd_tuple$_ = callme("var", c);
            vara = _$rapyd_tuple$_[0];
            varb = _$rapyd_tuple$_[1];
            """)

    def test_assigment_item_in_list(self):
        """
        Make sure this still works
        """
        self.check("""
        def f(self):
            myself = [0, 1, 2]
            myself[1] = 4
        """, """
        f = function() {
          var myself;
          myself = [0, 1, 2];
          myself[1] = 4;
        };
        """)

    def test_assigment_left_three(self):
        self.check("""
            vara, varb,varc = callme('var', c)
            """, """
            _$rapyd_tuple$_ = callme("var", c);
            vara = _$rapyd_tuple$_[0];
            varb = _$rapyd_tuple$_[1];
            varc = _$rapyd_tuple$_[2];
            """)

    def test_assigment_right_three(self):
        self.check("""
            packed_tuple = vara,'testme', 2,callable(2,3)
            """, """
            packed_tuple = [vara, "testme", 2, callable(2, 3)];
            """)

    def test_for_loop_unpacking(self):
        self.check("""
            for vara,varb in input_list:
                pass
            """, """
            var _$tmp1_data = _$rapyd$_iter(input_list);
            var _$tmp2_len = _$tmp1_data.length;
            for (var _$tmp3_index = 0; _$tmp3_index < _$tmp2_len; _$tmp3_index++) {
              _$rapyd$_tuple = _$tmp1_data[_$tmp3_index];
              vara = _$rapyd$_tuple[0];
              varb = _$rapyd$_tuple[1];
            }
            """)

    def test_for_loop_packing(self):
        self.check("""
            for input in 'inputa', obj.call2(), vara, 9.2:
                pass
            """, """
            var _$tmp1_data = _$rapyd$_iter(["inputa", obj.call2(), vara, 9.2]);
            var _$tmp2_len = _$tmp1_data.length;
            for (var _$tmp3_index = 0; _$tmp3_index < _$tmp2_len; _$tmp3_index++) {
              input = _$tmp1_data[_$tmp3_index];
            }
            """)

class TestListComprehensions(PyvaTest):
	def test_to_and_til(self):
		self.check("""
			a = [1 to 5]
		""","""
			a = range(1, 5+1);
		""")
		self.check("""
			a = [1 til 5]
		""","""
			a = range(1, 5);
		""")
		self.check("""
			a = [1 + 2 to 5 * 6]
		""","""
			a = range((1 + 2), (5 * 6)+1);
		""")
		self.check("""
		for i in [4 til 10]:
			pass
		""","""
		var _$tmp1_data = _$rapyd$_iter(range(4, 10));
		var _$tmp2_len = _$tmp1_data.length;
		for (var _$tmp3_index = 0; _$tmp3_index < _$tmp2_len; _$tmp3_index++) {
		  i = _$tmp1_data[_$tmp3_index];
		}
		""")

class TestNonlocalKeyword(PyvaTest):
    def test_return_normal_not_packed(self):
        self.check("""
        def():
            x = 2
            def ():
                y = 5
        """, """
        function() {
          var x;
          x = 2;
          function() {
            var y;
            y = 5;
          }
        }
        """)
        self.check("""
        def():
            x = 2
            def ():
                nonlocal y
                y = 5
        """, """
        function() {
          var x;
          x = 2;
          function() {
            y = 5;
          }
        }
        """)


class Test(PyvaTest):
    def test_in(self):
        self.check('x in y', '(x in y);')
        self.check('x not in y', '!(x in y);')

    def test_len(self):
        self.check('len(x)', 'x.length;')

    def test_dot(self):
        self.check('x.y.z', 'x.y.z;')

    def test_delete(self):
        self.check('del x[a]', 'delete x[a];')
        self.check("del x['a']", "delete x[\"a\"];")
        self.check('del x.a', 'delete x.a;')

    def test_getitem(self):
        self.check('x[0]', 'x[0];')
        self.check('x[0][bla]', 'x[0][bla];')

    def test_negative_getitem_special(self):
        self.check('x[-1]', 'x.slice(-1)[0];')
        self.check('x[-2]', 'x.slice(-2, -1)[0];')

    def test_slicing(self):
        self.check('x[:]', 'x.slice(0);')
        self.check('x[3+3:]', 'x.slice((3 + 3));')
        self.check('x[3+3:]', 'x.slice((3 + 3));')
        self.check('x[:10]', 'x.slice(0, 10);')
        self.check('x[5:10]', 'x.slice(5, 10);')

    def test_hasattr(self):
        self.check('hasattr(x, y)', '(typeof x[y] != "undefined");')
        self.check('not hasattr(x, y)', '(typeof x[y] == "undefined");')

    def test_getattr(self):
        self.check('getattr(x, y)', 'x[y];')

    def test_setattr(self):
        self.check('setattr(x, y, z)', 'x[y] = z;')

    def test_dot_getitem(self):
        self.check('x.y[0]', 'x.y[0];')
        self.check('x.y[0].z', 'x.y[0].z;')
        self.check('x.y[0].z[214]', 'x.y[0].z[214];')

    def test_call_dot_getitem(self):
        self.check('x.f().y[0]', 'x.f().y[0];')
        self.check('x.y[0].z()', 'x.y[0].z();')
        self.check('x.y[0].z[214].f().a', 'x.y[0].z[214].f().a;')

    def test_floats(self):
        self.check('2.3 * 1.4', '(2.3 * 1.4);')

    def test_assign_call_dot_getitem(self):
        self.check('a = x.f().y[0]', 'a = x.f().y[0];')
        self.check('a = x.y[0].z()', 'a = x.y[0].z();')
        self.check('a = x.y[0].z[214].f().a', 'a = x.y[0].z[214].f().a;')
        self.check('a += x.y[0].z[214].f().a', 'a += x.y[0].z[214].f().a;')

    def test_return(self):
        self.check("""
        def():
            return
        """, """
        function() {
          return;
        }
        """)

        self.check("""
        def():
            return x
        """, """
        function() {
          return x;
        }
        """)

    def test_return_expression(self):
        self.check("""
        def():
            return a < 5 and 6 >= b or 2 <= 8
        """, """
        function() {
          return (((a < 5) && (6 >= b)) || (2 <= 8));
        }
        """)

    def test_if(self):
        self.check("""
        if a == 3 or b is None and c == True or d != False:
            f()
        """, """
        if ((((a == 3) || ((b === null) && (c == true))) || (d != false))) {
          f();
        }
        """)

        self.check("""
        if a < 5 and 6 >= b or 2 <= 8:
            f()
        """, """
        if ((((a < 5) && (6 >= b)) || (2 <= 8))) {
          f();
        }
        """)
        
        self.check("""
        if(a < 5):
            f()
        """, """
        if ((a < 5)) {
          f();
        }
        """)

    def test_while(self):
        self.check("""
        while a == 3 or b is None and c == True or d != False:
            f()
            if x:
                break
            continue
        """, """
        while ((((a == 3) || ((b === null) && (c == true))) || (d != false))) {
          f();
          if (x) {
            break;
          }

          continue;
        }
        """)

        self.check("""
        while(a == 3):
            f()
        """, """
        while ((a == 3)) {
          f();
        }
        """)

    def test_for_range_literal(self):
        self.check("""
        for i in range(10):
            f()
        """, """
        for (i = 0; i < 10; i++) {
          f();
        }
        """)

        self.check("""
        for i in range(2, 10):
            f()
        """, """
        for (i = 2; i < 10; i++) {
          f();
        }
        """)

        self.check("""
        for i in range(2, 10, 2):
            f()
        """, """
        for (i = 2; i < 10; i += 2) {
          f();
        }
        """)

    def test_for_range_nonliteral(self):
        self.check("""
        for i in range(x(10)):
            f()
        """, """
        var _$tmp1_end = x(10);
        for (i = 0; i < _$tmp1_end; i++) {
          f();
        }
        """)

        self.check("""
        for i in range(x(2), x(10)):
            f()
        """, """
        var _$tmp1_end = x(10);
        for (i = x(2); i < _$tmp1_end; i++) {
          f();
        }
        """)

        self.check("""
        for i in range(x(2), x(10), x(2)):
            f()
        """, """
        var _$tmp1_end = x(10), _$tmp2_step = x(2);
        for (i = x(2); i < _$tmp1_end; i += _$tmp2_step) {
          f();
        }
        """)

    def test_for_reversed_range_literal(self):
        self.check("""
        for i in reversed(range(2, 10)):
            f()
        """, """
        for (i = (10) - 1; i >= 2; i--) {
          f();
        }
        """)

        self.check("""
        for i in reversed(range(2, 10, 2)):
            f()
        """, """
        for (i = (10) - 1; i >= 2; i -= 2) {
          f();
        }
        """)

    def test_for_reversed_range_nonliteral(self):
        self.check("""
        for i in reversed(range(x(10))):
            f()
        """, """
        i = x(10);
        while (i--) {
          f();
        }
        """)

        self.check("""
        for i in reversed(range(x(2), x(10))):
            f()
        """, """
        var _$tmp1_end = x(2);
        for (i = (x(10)) - 1; i >= _$tmp1_end; i--) {
          f();
        }
        """)

        self.check("""
        for i in reversed(range(x(2), x(10), x(2))):
            f()
        """, """
        var _$tmp1_end = x(2), _$tmp2_step = x(2);
        for (i = (x(10)) - 1; i >= _$tmp1_end; i -= _$tmp2_step) {
          f();
        }
        """)

    def test_for_in(self):
        self.check("""
        for i in x.y[10].z():
            f(i)
        """, """
        var _$tmp1_data = _$rapyd$_iter(x.y[10].z());
        var _$tmp2_len = _$tmp1_data.length;
        for (var _$tmp3_index = 0; _$tmp3_index < _$tmp2_len; _$tmp3_index++) {
          i = _$tmp1_data[_$tmp3_index];

          f(i);
        }
        """)

    def test_one_liners(self):
        self.check("""
        def f(): pass
        while True: pass
        for i in reversed(range(10)): pass
        """, """
        f = function() {
        };
        while (true) {
        }
        i = 10;
        while (i--) {
        }
        """)

    def test_simple_prototype(self):
        self.check("""
        x.prototype = {
            'add': def(self, a, b, c):
                return 1 + 2
            ,
        }
        """, """
        x.prototype = {
          "add": (function(a, b, c) {
            return (1 + 2);
          })
        };
        """)

    def test_multi_line_lambda(self):
        self.check("""
        x.prototype = {
            '__init__': def(self):
                def nested():
                    return None
                a = 3
                x = a + 3
                return x
            ,
            'add': def(self, a, b, c):
                return 1 + 2
            ,
        }
        """, """
        x.prototype = {
          "__init__": (function() {
            var a, nested, x;

            nested = function() {
              return null;
            };

            a = 3;
            x = (a + 3);
            return x;
          }),
          "add": (function(a, b, c) {
            return (1 + 2);
          })
        };
        """)

    def test_lambda_call(self):
        self.check("""
        (def():
            global x
            x = 5
        )()
        """, """
        (function() {
          x = 5;
        })();
        """)

    def test_self(self):
        self.check("""
        self.f()
        """, """
        self.f();
        """)

        self.check("""
        def f():
            self.f()
        """, """
        f = function() {
          self.f();
        };
        """)

        self.check("""
        def f(self):
            self.f()
        """, """
        f = function() {
          this.f();
        };
        """)

        self.check("""
        def f(self):
            myself = self
            def g():
                myself.f()
        """, """
        f = function() {
          var g, myself;
          myself = this;
          g = function() {
            myself.f();
          };
        };
        """)


if __name__ == '__main__':
    unittest.main()

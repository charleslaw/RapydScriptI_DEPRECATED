/* This file was auto-generated using RapydScript */
JSON = (JSON || {
  
});
if ((!JSON.stringify)) {
  
	JSON.stringify = function(obj) {
		var t = typeof (obj);
		if (t != "object" || obj === null) {
			// simple data type
			if (t == "string")
				obj = '"' + obj + '"';
			if (t == "function")
				return; // return undefined
			else
				return String(obj);
		} else {
			// recurse array or object
			var n, v, json = []
			var arr = (obj && obj.constructor == Array);
			for (n in obj) {
				v = obj[n];
				t = typeof (v);
				if (t != "function" && t != "undefined") {
					if (t == "string")
						v = '"' + v + '"';
					else if ((t == "object" || t == "function") && v !== null)
						v = JSON.stringify(v);
					json.push((arr ? "" : '"' + n + '":') + String(v));
				}
			}
			return (arr ? "[" : "{") + String(json) + (arr ? "]" : "}");
		}
	};
	
}

range = function(a, b, step) {
  var A;
  A = [];
  if ((typeof(b) === "undefined")) {
    b = a;
    a = 0;
  }

  A[0] = a;
  step = (step || 1);
  if ((step > 0)) {
    while (((a + step) < b)) {
      a += step;
      A[A.length] = a;
    }

  } else {
    while (((a + step) > b)) {
      a += step;
      A[A.length] = a;
    }

  }

  return A;
};

enumerate = function(item) {
  var A;
  A = [];
  for (var i = 0; i < item.length; i++){A[A.length] = [i, item[i]];}
  return A;
};

reversed = function(arr) {
  var temp;
  temp = [];
  for (var i = arr.length - 1; i >= 0; i--) {temp.push(arr[i]);}
  return temp;
};

print = function() {
  var args, output;
  args = [].slice.call(arguments, 0);
  output = JSON.stringify(args);
  console.log(output.substr(1, (output.length - 2)));
};


isinstance = function(item, cls) {
	return item instanceof cls;
};
_$rapyd$_iter = function(iter_object) {
	if (iter_object instanceof Array) {
		return iter_object;
	}

	var key_list = [];
	for (var key in iter_object) {
		if (iter_object.hasOwnProperty(key)) {
			key_list.push(iter_object[key]);
		}
	}
	return key_list;
};
Function.prototype.bind = (function(owner) {
	var bound, func;
	func = this;
	bound = function() {
		return func.apply(owner, arguments);
	};

	return bound;
});

ValueError = function(message) {
  this.name = "ValueError";
  this.message = message;
};

ValueError.prototype = new Error();
ValueError.prototype.constructor = ValueError;
str = function(elem) {
  if (typeof elem === "undefined") {elem = ""};
  this._str = String(elem)
};

str.prototype.strip = (function() {
  return new str(this._str.trim());
});
str.prototype.lstrip = (function() {
  return new str(this._str.trimLeft());
});
str.prototype.rstrip = (function() {
  return new str(this._str.trimRight());
});
str.prototype.join = (function(iterable) {
  return new str(iterable.join(this._str));
});
str.prototype.zfill = (function(size) {
  var s;
  s = this;
  while ((s.length < size)) {
    s = ("0" + s);
  }

  return new str(s);
});
str.prototype.replace = (function(orig, sub, n) {
  var s;
  if (n) {
    s = this;
    var _$tmp1_end = n.length;
    for (n = 0; n < _$tmp1_end; n++) {
      s = String.prototype.replace.call(s, orig, sub);
    }

  } else {
    s = String.prototype.replace.call(this, new RegExp(orig, "g"), sub);
  }

  return new str(s);
});
str.prototype.toString = (function() {
  return this._str;
});
str.prototype.valueOf = (function() {
  return this._str;
});
list = function(iterable) {
  var elem;
  var _$tmp2_data = _$rapyd$_iter(iterable);
  var _$tmp3_len = _$tmp2_data.length;
  for (var _$tmp4_index = 0; _$tmp4_index < _$tmp3_len; _$tmp4_index++) {
    elem = _$tmp2_data[_$tmp4_index];

    Array.prototype.push.call(this, elem);
  }

};

list.prototype = new Array();
list.prototype.constructor = list;
list.prototype.append = (function(elem) {
  this.push(elem);
});
list.prototype.find = (function(elem) {
  return this.indexOf(elem);
});
list.prototype.index = (function(elem) {
  var val;
  val = this.find(elem);
  if ((val == (-1))) {
    throw new ValueError((new str(elem) + " is not in list"));
  }

  return val;
});
list.prototype.insert = (function(index, elem) {
  this.splice(index, 0, elem);
});
list.prototype.pop = (function(index) {
  if (typeof index === "undefined") {index = len(this)-1};
  return this.splice(index, 1)[0];
});
list.prototype.extend = (function(list2) {
  this.push.apply(this, [].concat(list2));
});
list.prototype.remove = (function(elem) {
  var index;
  index = this.find(elem);
  this.pop(index);
});
list.prototype.copy = (function() {
  return new list(this);
});
if ((!Array.prototype.map)) {
  
	Array.prototype.map = function(callback, thisArg) {
		var T, A, k;
		if (this == null) {
			throw new TypeError(" this is null or not defined");
		}
		var O = Object(this);
		var len = O.length >>> 0;
		if ({}.toString.call(callback) != "[object Function]") {
			throw new TypeError(callback + " is not a function");
		}
		if (thisArg) {
			T = thisArg;
		}
		A = new Array(len);
		for (var k = 0; k < len; k++) {
			var kValue, mappedValue;
			if (k in O) {
				kValue = O[k];
				mappedValue = callback.call(T, kValue);
				A[k] = mappedValue;
			}
		}
		return A;
	};
	
}

map = function(oper, arr) {
  return new list(arr.map(oper));
};

if ((!Array.prototype.filter)) {
  
	Array.prototype.filter = function(filterfun, thisArg) {
		"use strict";
		if (this == null) {
			throw new TypeError(" this is null or not defined");
		}
		var O = Object(this);
		var len = O.length >>> 0;
		if ({}.toString.call(filterfun) != "[object Function]") {
			throw new TypeError(filterfun + " is not a function");
		}
		if (thisArg) {
			T = thisArg;
		}
		var A = [];
		var thisp = arguments[1];
		for (var k = 0; k < len; k++) {
			if (k in O) {
				var val = O[k]; // in case fun mutates this
				if (filterfun.call(T, val))
					A.push(val);
			}
		}
		return A;
	};
	
}

filter = function(oper, arr) {
  return new list(arr.filter(oper));
};

var _$rapyd$_getOwnProps = Object.getOwnPropertyNames
dict = function(hashlike) {
  var key;
  var _$tmp5_data = _$rapyd$_iter(hashlike);
  var _$tmp6_len = _$tmp5_data.length;
  for (var _$tmp7_index = 0; _$tmp7_index < _$tmp6_len; _$tmp7_index++) {
    key = _$tmp5_data[_$tmp7_index];

    this[key] = hashlike[key];
  }

};

dict.prototype = new Object();
dict.prototype.constructor = dict;
dict.prototype.keys = (function() {
  var keys;
  if ((typeof(_$rapyd$_getOwnProps) === "function")) {
    return _$rapyd$_getOwnProps(this);
  } else {
    keys = [];
    
		for (var x in hash) {
			if (this.hasOwnProperty(x)) {
				keys.push(x);
			}
		}
		
    return keys;
  }

});
dict.prototype.values = (function() {
  var key, vals;
  vals = [];
  var _$tmp8_data = _$rapyd$_iter(dict.prototype.keys.call(this));
  var _$tmp9_len = _$tmp8_data.length;
  for (var _$tmp10_index = 0; _$tmp10_index < _$tmp9_len; _$tmp10_index++) {
    key = _$tmp8_data[_$tmp10_index];

    vals.push(this[key]);
  }

  return vals;
});
dict.prototype.items = (function() {
  var items, key;
  items = [];
  var _$tmp11_data = _$rapyd$_iter(dict.prototype.keys.call(this));
  var _$tmp12_len = _$tmp11_data.length;
  for (var _$tmp13_index = 0; _$tmp13_index < _$tmp12_len; _$tmp13_index++) {
    key = _$tmp11_data[_$tmp13_index];

    items.push([key, this[key]]);
  }

  return items;
});
dict.prototype.copy = (function() {
  return new dict(this);
});
dict.prototype.clear = (function() {
  var key;
  var _$tmp14_data = _$rapyd$_iter(dict.prototype.keys.call(this));
  var _$tmp15_len = _$tmp14_data.length;
  for (var _$tmp16_index = 0; _$tmp16_index < _$tmp15_len; _$tmp16_index++) {
    key = _$tmp14_data[_$tmp16_index];

    delete this[key];
  }

});

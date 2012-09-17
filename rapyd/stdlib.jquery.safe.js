// basic
_$pyva_int = parseInt;
_$pyva_float = parseFloat;
str = JSON.stringify;
function len(item) {
  return item.length;
}
range = function(a, b, step){
    var A = [];
	A[0] = a;
	step = step || 1;
	while(a+step <= b){
		A[A.length] = a += step;
	}
};
function reversed(arr) {
  var temp = new Array();
  for (var i = arr.length - 1; i >= 0; i--) {
    temp.push(arr[i]);
  }
  return temp;
}
function print() {
  var argsArray = [].slice.apply(arguments);
  var output = JSON.stringify(argsArray);
  console.log(output.substr(1, output.length-2));
}
isinstance = function(item, cls) {
  var cls_item, isnumber;
  if (cls instanceof Array) {
    var _$tmp13_data = _$pyva_iter(cls);
    var _$tmp14_len = _$tmp13_data.length;
    for (var _$tmp15_index = 0; _$tmp15_index < _$tmp14_len; _$tmp15_index++) {
      cls_item = _$tmp13_data[_$tmp15_index];

      if (isinstance(item, cls_item)) {
        return true;
      }

    }

    return false;
  }

  if ((cls === list)) {
    cls = Array;
  } else if ((cls === dict)) {
    cls = Object;
  } else if ((cls === str)) {
    cls = String;
  } else if (((cls === _$pyva_int) || (cls === _$pyva_float))) {
    isnumber = (item.constructor === Number.prototype.constructor);
    return (isnumber && (cls(item) == item));
  } else {
    return item instanceof cls;
  }

  return (item.constructor === cls.prototype.constructor);
};
_$pyva_iter = function(iter_object) {
  var key_list;
  if (((iter_object.callee && (typeof iter_object['length'] != "undefined")) || isinstance(iter_object, list))) {
    return iter_object;
  }

  key_list = [];
  for (var key in iter_object)
  key_list.append(key);
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
function type(object) {
  return typeof(object);
}

// string
String.prototype.strip = String.prototype.trim;
String.prototype.lstrip = String.prototype.trimLeft;
String.prototype.rstrip = String.prototype.trimRight;
String.prototype.join = function (iterable) {
  return iterable.join(this);
};

// array
list = function(x) {
  var item, result;
  result = [];
  var _$tmp1_data = _$pyva_iter(x);
  var _$tmp2_len = _$tmp1_data.length;
  for (var _$tmp3_index = 0; _$tmp3_index < _$tmp2_len; _$tmp3_index++) {
    item = _$tmp1_data[_$tmp3_index];

    result.append(item);
  }

  return result;
};
Array.prototype.append = Array.prototype.push;
Array.prototype.index = Array.prototype.indexOf;
Array.prototype.insert = function(index, item) { this.splice(index, 0, item); };
Array.prototype.pop = function(index) { if (!arguments.length) { index = this.length-1; } return this.splice(index, 1)[0]; };
Array.prototype.extend = function(array2) { this.push.apply(array2); };
Array.prototype.remove = function(item) { var index = this.indexOf(item); this.splice(index, 1); };
Array.prototype.find = Array.prototype.indexOf;
Array.prototype.copy = function() {return this.slice(0);};

// dict (this is a bit of a hack for now, to avoid overwriting the Object)
// the methods below must be used via dict.method(object) instead of object.method()
dict = function(x) {
  var key, result;
  result = {
    
  };
  var _$tmp4_data = _$pyva_iter(x);
  var _$tmp5_len = _$tmp4_data.length;
  for (var _$tmp6_index = 0; _$tmp6_index < _$tmp5_len; _$tmp6_index++) {
    key = _$tmp4_data[_$tmp6_index];

    result[key] = x[key];
  }

  return result;
};
if (typeof Object.getOwnPropertyNames !== "function") {
	// IE and older browsers
    dict.keys = function (hash) {
        var keys = [];

        // Use a standard for in loop
        for (var x in hash) {
            // A for in will iterate over members on the prototype
            // chain as well, but Object.getOwnPropertyNames returns
            // only those directly on the object, so use hasOwnProperty.
            if (hash.hasOwnProperty(x)) {
                keys.push(x);
            }
        }

        return keys;
    }
} else {
	// normal browsers
    dict.keys = function(hash) {
    	return Object.getOwnPropertyNames(hash)
    };
}
dict.values = function(hash) {
    var vals = [];
    
    for (var x in hash) {
        if (hash.hasOwnProperty(x)) {
            vals.push(hash[x]);
        }
    };
    
    return vals;
};
dict.copy = function(hash) {
    var copy = {};
    
    for(var x in hash) {
        if (this.hasOwnProperty(x)) {
            copy[x] = hash[x];
        }
    }
    
    return copy;
};
dict.clear = function(hash) {
    for (var x in hash) {
        if (this.hasOwnProperty(x)) {
            delete hash[x];
        }
    }
};

from tutor.audio.sanitizer import apply


def test_list_of_strings():
    assert apply("Use List<String> here") == "Use a List of Strings here"


def test_hashmap():
    assert apply("HashMap<String, Integer>") == "a HashMap from String to Integer"


def test_not_equal():
    assert apply("if (a != b)") == "if (a not equal to b)"


def test_double_equals():
    assert apply("if (a == b)") == "if (a double equals b)"


def test_annotation():
    assert apply("@Override") == "Override annotation"


def test_int_array():
    assert apply("int[] arr") == "int array arr"


def test_null_pointer():
    assert apply("throws NullPointerException") == "throws Null Pointer Exception"


def test_no_change():
    result = apply("Java is a statically typed language")
    assert result == "Java is a statically typed language"


def test_multiple_substitutions():
    result = apply("List<String> with != and ==")
    assert "a List of Strings" in result
    assert "not equal to" in result
    assert "double equals" in result

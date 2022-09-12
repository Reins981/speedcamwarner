

class A:
    web = None

def test1():
    A.web = 333

def test2():
    A.web = 444

test1()
test2()
print(A.web)

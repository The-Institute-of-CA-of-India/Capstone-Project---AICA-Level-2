"""A small, safe formula checker, deliberately not an Excel engine."""
import ast
import re

def calculate(formula, cells):
    if not isinstance(formula, str) or len(formula) > 160 or not formula.startswith('='):
        raise ValueError('Start with = and use at most 160 characters.')
    expression = formula[1:].upper().replace('$', '')
    def function(match):
        name, first, last = match.groups()
        lo, hi = int(first), int(last)
        if not 2 <= lo <= hi <= 5:
            raise ValueError('Supported ranges are within B2:B5.')
        values = [cells[f'B{i}'] for i in range(lo, hi + 1)]
        results = dict(SUM=sum(values), AVERAGE=sum(values)/len(values), MIN=min(values), MAX=max(values), COUNT=len(values))
        return str(results[name])
    expression = re.sub(r'\b(SUM|AVERAGE|MIN|MAX|COUNT)\s*\(\s*B([2-5]):B([2-5])\s*\)', function, expression)
    expression = re.sub(r'\bB[2-5]\b', lambda m: str(cells[m[0]]), expression)
    tree = ast.parse(expression, mode='eval')
    operations = {ast.Add: lambda a,b:a+b, ast.Sub:lambda a,b:a-b, ast.Mult:lambda a,b:a*b, ast.Div:lambda a,b:a/b}
    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float) and abs(node.value) <= 1000000:
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        raise ValueError('Use only B2:B5, numbers, + - * /, parentheses, or the five supported range functions.')
    return evaluate(tree.body)

def grade(lesson_id, answer):
    if not isinstance(answer, str):
        return False, 'Enter a text answer.'
    if lesson_id < 4:
        expected = {1:'B2:B5',2:'ENTER',3:'25%'}[lesson_id]
        ok = answer.upper().replace(' ', '').replace('$','') == expected
        return ok, ('Well done! Your answer is correct.' if ok else 'Not quite yet. Try a hint and check the lesson example.')
    try:
        for numbers in [(40,20,8,12),(10,7,3,5),(0,4,9,2),(12.5,0,2.5,1)]:
            cells = dict(zip(['B2','B3','B4','B5'], numbers))
            target = (numbers[0]+numbers[1])*2 if lesson_id == 4 else sum(numbers)
            if abs(calculate(answer, cells)-target) > 1e-8:
                return False, 'This formula does not work for every test set. Reference the input cells so changes update the result.'
        return True, 'Correct across four input sets! Your formula follows the changing inputs.'
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError):
        return False, 'Formula not supported or invalid. Use B2:B5, numbers, + - * /, parentheses, or SUM/AVERAGE/MIN/MAX/COUNT on a contiguous B2:B5 range.'

// @ts-nocheck
// test.ts
const MY_VAR: number = 42;
const arrowFunc = (x: number, y: number = 10): number => {
    let z = x + y;
    console.log(`Result: ${z}`);
    return z;
};
class MyClass {
    classVar: string = "test";
    constructor(param: string) {
        this.classVar = param;
    }
    myMethod(x: number): void {
        console.log(`Method: ${x}`);
    }
}

// Additional test cases
const asyncArrow = async (a: string = "hello", b?: number): Promise<string> => {
    let temp = a.length + (b || 0);
    console.log(temp);
    return a;
};
interface MyInterface {
    id: number;
}
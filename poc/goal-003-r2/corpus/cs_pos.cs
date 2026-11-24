using System;
public class Sample {
    public object Bad(bool flag) {
        try {
            if (flag == true) {
                Console.WriteLine("x");
                goto end;
            }
        } catch (Exception) { }
    end:
        return new object();
    }
}

public class BadJava {
    public Object run(boolean flag, int a, int b, int c, int d, int e) {
        try {
            if (flag == true) {
                System.out.println("hi");
            }
        } catch (Exception ex) { }
        return null;
    }
}

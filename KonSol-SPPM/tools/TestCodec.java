package io.github.aidevelopersmonster.konsolsppm;
import java.util.Arrays;
public final class TestCodec {
    private static void check(boolean ok,String name){
        if(!ok)throw new AssertionError(name);
        System.out.println("PASS: "+name);
    }
    public static void main(String[] args){
        MacroCommand m=new MacroCommand("LED ON","A5 01 01",true,"CRLF");
        check(Arrays.equals(m.payload(),new byte[]{(byte)0xA5,1,1}),"fixed button HEX bytes");
        MacroCommand t=new MacroCommand("STATUS","STATUS",false,"LF");
        check(Arrays.equals(t.payload(),new byte[]{83,84,65,84,85,83,10}),"fixed button TEXT LF");
        check(MacroCommand.defaultFor(5).command.isEmpty(),"unassigned macro empty");
        check(Arrays.equals(HexCodec.parse("AA 00 FF"),new byte[]{(byte)0xAA,0,(byte)0xFF}),"hex bytes");
        check(Arrays.equals(HexCodec.parse("0xAA,0x00,0xFF"),new byte[]{(byte)0xAA,0,(byte)0xFF}),"0x prefix");
        check(HexCodec.display(new byte[]{1,(byte)0xFF}).equals("01 FF"),"display");
        check(Arrays.equals(HexCodec.text("KON","CRLF"),new byte[]{75,79,78,13,10}),"text CRLF");
        boolean odd=false;try{HexCodec.parse("F");}catch(IllegalArgumentException e){odd=true;}check(odd,"reject odd digits");
        boolean invalid=false;try{HexCodec.parse("1G");}catch(IllegalArgumentException e){invalid=true;}check(invalid,"reject invalid hex");
    }
}

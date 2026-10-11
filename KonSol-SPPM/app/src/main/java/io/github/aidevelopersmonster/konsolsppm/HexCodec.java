package io.github.aidevelopersmonster.konsolsppm;
import java.nio.charset.StandardCharsets;
public final class HexCodec {
    private static final char[] DIGITS="0123456789ABCDEF".toCharArray();
    private HexCodec(){}
    public static byte[] parse(String text) {
        if(text==null) throw new IllegalArgumentException("HEX: пустая строка");
        String compact=text.replaceAll("(?i)0x","").replaceAll("[\\s,;:_-]","");
        if(compact.isEmpty())throw new IllegalArgumentException("HEX: нет байтов");
        if((compact.length()&1)!=0)throw new IllegalArgumentException("HEX: нечётное число цифр");
        byte[] r=new byte[compact.length()/2];
        for(int i=0;i<r.length;i++){
            int hi=Character.digit(compact.charAt(2*i),16),lo=Character.digit(compact.charAt(2*i+1),16);
            if(hi<0||lo<0)throw new IllegalArgumentException("HEX: неверный байт "+(i+1));
            r[i]=(byte)((hi<<4)|lo);
        }return r;
    }
    public static String display(byte[] data){
        if(data==null||data.length==0)return "";
        StringBuilder b=new StringBuilder(data.length*3);
        for(int i=0;i<data.length;i++){
            if(i>0)b.append(' ');
            int v=data[i]&255;b.append(DIGITS[v>>>4]).append(DIGITS[v&15]);
        }return b.toString();
    }
    public static byte[] text(String data,String eol){
        String suffix;
        switch(eol){case "CR":suffix="\r";break;case "LF":suffix="\n";break;case "CRLF":suffix="\r\n";break;default:suffix="";}
        return (data+suffix).getBytes(StandardCharsets.UTF_8);
    }
}

// Stock host observer target-instruction tests; offline. Native B2 helper bytes only injected.
// @category A1.IsolatedCore
import ghidra.app.script.GhidraScript;
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.emulator.MemoryAccessFilter;
import ghidra.program.model.address.AddressSpace;
import java.security.MessageDigest;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.RegisterValue;
import java.math.BigInteger;
import java.lang.reflect.Field;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

public class PMHistoryExecute extends GhidraScript {
 static final long STATE=0x2007fd80L, STACK=0x20060000L, INPUT=0x20050000L, RETURN=0x20040000L;
 static final long INITIAL_FLAGS=0xa8000000L;
 long initialSP=STACK-1024; int primask; byte[] finalApp; long deepestStack=0; int maximumStack=0; int maskWindowChecks=0; boolean metrics=false; int dataReads=0,dataWrites=0,flashReads=0,modeReads=0; EmulatorHelper e; Map<String,Long> symbols;
 String sha(Path p)throws Exception{byte[]d=MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p));StringBuilder b=new StringBuilder();for(byte x:d)b.append(String.format("%02x",x&255));return b.toString();}
 void boundedMemory(){
  MemoryAccessFilter f=new MemoryAccessFilter(){
   boolean in(long p,int n,long lo,long hi){return p>=lo&&p+n<=hi;}
   protected void processRead(AddressSpace sp,long p,int n,byte[]b){if(!sp.isMemorySpace())return;check(in(p,n,0,0x110000L)||in(p,n,0x20000000L,0x20080000L),"unexpected read "+Long.toHexString(p));}
   protected void processWrite(AddressSpace sp,long p,int n,byte[]b){if(!sp.isMemorySpace())return;
    boolean stack=in(p,n,STACK-8192,STACK);boolean state=in(p,n,STATE,STATE+512);boolean output=in(p,n,INPUT,INPUT+4096);
    check(stack||state||output,"write outside observer/stack/readout "+Long.toHexString(p));
    if(stack&&p<initialSP)deepestStack=Math.max(deepestStack,initialSP-p);
    if(state)check(primask==1,"unmasked observer write");
   }
  };f.setFilterOnExecutionOnly(true);e.getEmulator().addMemoryAccessFilter(f);
 }
 void thumbOnlyAdapter() throws Exception {
  // Ghidra12.1 ARM setISAMode modifier calls setContextRegisterValue during
  // EXECUTE and throws "emulator is not STOPPED" on BX/POP. All decoded core
  // control-flow targets are Thumb. Replace only that architectural-mode
  // modifier with a checked Thumb-only userop, retaining Sleigh branch/RAM ops.
  Field inner=e.getEmulator().getClass().getDeclaredField("emulator");inner.setAccessible(true);Object em=inner.get(e.getEmulator());
  Field modifier=em.getClass().getDeclaredField("instructionStateModifier");modifier.setAccessible(true);modifier.set(em,null);
  e.registerCallOtherCallback("setISAMode",new BreakCallBack(){public boolean pcodeCallback(PcodeOpRaw op){check(reg("TB")==1,"unsupported attempted ARM-state exchange");return true;}});
 }

 long u32(long x){return x&0xffffffffL;}
 Address a(long x){return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(u32(x));}
 void check(boolean v,String why){if(!v)throw new IllegalStateException(why);}
 long word(long p){byte[] b=e.readMemory(a(p),4);return ((b[0]&255L)|((b[1]&255L)<<8)|((b[2]&255L)<<16)|((b[3]&255L)<<24));}
 long reg(String r){return u32(e.readRegister(r).longValue());}
 long flags(){return (reg("NG")<<31)|(reg("ZR")<<30)|(reg("CY")<<29)|(reg("OV")<<28)|(reg("Q")<<27);}
 void flags(long v){e.writeRegister("NG",(v>>>31)&1);e.writeRegister("ZR",(v>>>30)&1);e.writeRegister("CY",(v>>>29)&1);e.writeRegister("OV",(v>>>28)&1);e.writeRegister("Q",(v>>>27)&1);}
 void skip(long p,int n){e.getEmulator().setExecuteAddress(p+n);e.setContextRegister(currentProgram.getRegister("TMode"),BigInteger.ONE);}
 boolean system(long pc){
  byte[] b=e.readMemory(a(pc),4);int h=(b[0]&255)|((b[1]&255)<<8);int z=(b[2]&255)|((b[3]&255)<<8);
  if(h==0xb672){primask=1;skip(pc,2);return true;}
  if(h==0xb662)throw new IllegalStateException("unexpected unconditional CPSIE");
  if(h==0xf3ef && (z&0xf0ff)==0x8010){e.writeRegister("r"+((z>>>8)&15),primask);skip(pc,4);return true;}
  if(h==0xf3ef && (z&0xf0ff)==0x8000){e.writeRegister("r"+((z>>>8)&15),flags());skip(pc,4);return true;}
  if((h&0xfff0)==0xf380 && z==0x8810){primask=(int)(reg("r"+(h&15))&1);skip(pc,4);return true;}
  if((h&0xfff0)==0xf380 && z==0x8800){flags(reg("r"+(h&15)));skip(pc,4);return true;}
  if(h==0xf3bf && (z==0x8f5f || z==0x8f4f || z==0x8f6f)){skip(pc,4);return true;}
  return false;
 }
 int tests=0; JsonArray cases=new JsonArray(); JsonArray snapshots=new JsonArray();byte[] baseline;
 long SP=STACK-1024,FP=STACK-768;int maximumEventStack=0; int maximumEventSteps=0;
 void put(long p,long v){e.writeMemoryValue(a(p),4,v);}
 void bytePut(long p,int v){e.writeMemory(a(p),new byte[]{(byte)v});}
 long state(int i){return word(STATE+4L*i);}void state(int i,long v){put(STATE+4L*i,v);}
 void fresh(boolean patched)throws Exception{
  e=new EmulatorHelper(currentProgram);thumbOnlyAdapter();boundedMemory();e.writeMemory(a(0),patched?finalApp:baseline);
  e.writeMemory(a(STACK-8192),new byte[8192]);e.writeMemory(a(INPUT),new byte[8192]);e.writeMemory(a(STATE),new byte[512]);
  e.writeMemory(a(0x2007ff80L),new byte[128]);state(0,0x504d3636L);state(1,1);state(2,512);state(5,1);state(6,1);put(0x20001858,12345);
 }
 void entry(long pc,int mask,long fl){
  primask=mask;initialSP=SP;deepestStack=0;
  for(int i=0;i<=12;i++)e.writeRegister("r"+i,0x41000000L+i);
  e.writeRegister("sp",SP);e.writeRegister("r7",FP);e.writeRegister("lr",RETURN|1);flags(fl);
  e.setContextRegister(new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO));e.setContextRegister(currentProgram.getRegister("TMode"),BigInteger.ONE);e.writeRegister("TB",1);e.getEmulator().setExecuteAddress(pc);
 }
 int steps(long stop)throws Exception{int n=0;while(e.getExecutionAddress().getOffset()!=stop){long pc=e.getExecutionAddress().getOffset();check(n++<20000,"bounded at "+Long.toHexString(pc));if(system(pc))continue;e.setContextRegister(currentProgram.getRegister("TMode"),BigInteger.ONE);if(!e.step(monitor))throw new IllegalStateException("Sleigh "+Long.toHexString(pc)+" "+e.getLastError());}return n;}
 long[] regs(){long[]v=new long[16];for(int k=0;k<=12;k++)v[k]=reg("r"+k);v[13]=reg("sp");v[14]=reg("lr");v[15]=flags();return v;}
 void same(long[]v,String name){long[]w=regs();for(int k=0;k<w.length;k++)check(v[k]==w[k],name+" ABI index"+k+" "+Long.toHexString(v[k])+" != "+Long.toHexString(w[k]));}
 void pass(String n){tests++;JsonObject c=new JsonObject();c.addProperty("name",n);c.addProperty("status","PASS");cases.add(c);}
 void setup(long hook,int arg){
  if(hook==0x1bd6){e.writeRegister("r0",0x52);e.writeRegister("r1",FP+8);e.writeRegister("r2",8);e.writeRegister("r3",0);put(SP,0);put(FP+8,0x00140101);put(FP+12,0);}
  if(hook==0x1bda||hook==0x1e108)e.writeRegister("r0",arg);
  if(hook==0x1e132){long delta=arg;e.writeRegister("r2",1000+delta);e.writeRegister("r3",delta);put(FP+48,delta);state(16,0);state(21,256);state(22,1);}
  if(hook==0x57fc4||hook==0x58120){put(FP+4,INPUT);put(INPUT+8,0x12345678);put(INPUT+12,0x9abc);put(INPUT+4,0xabcdef01);}
  if(hook==0x102f88){put(SP,0x68000000);put(SP+4,0x44444444);state(6,2);state(15,FP);}
  if(hook==0x103aee||hook==0x103b84){e.writeRegister("r0",arg);e.writeRegister("r4",INPUT);put(INPUT+16,0x12345);put(SP+12,7);put(SP+16,9);}
 }
 long stop(long h,int arg){if(h==0x1bd6)return 0x1e90;if(h==0x1bda)return 0x1bde;if(h==0x1e104)return 0x1cb4;if(h==0x1e108)return 0x1e10c;if(h==0x1e132)return 0x1e13c;if(h==0x57fc4)return 0x102f6c;if(h==0x58120)return 0x102f90;if(h==0x102f88)return 0x102f8e;if(h==0x103aee)return arg==0?0x103b50:0x103af2;if(h==0x103b84)return 0x103b88;throw new IllegalArgumentException();}
 void invoke(long hook,int mask,int arg)throws Exception{entry(hook,mask,INITIAL_FLAGS);setup(hook,arg);steps(stop(hook,arg));check(primask==mask,"maskrestore");check(deepestStack<=32,"event32");}
 public void run()throws Exception{
  String[]p=getScriptArgs();check(p.length==4,"symbols baseline final result");symbols=new HashMap<>();for(Map.Entry<String,JsonElement>x:JsonParser.parseString(Files.readString(Path.of(p[0]))).getAsJsonObject().entrySet())symbols.put(x.getKey(),Long.decode(x.getValue().getAsString()));baseline=Files.readAllBytes(Path.of(p[1]));finalApp=Files.readAllBytes(Path.of(p[2]));String error=null;
  try{
   for(long h:new long[]{0x1bd6,0x1bda,0x1e104,0x1e108,0x1e132,0x57fc4,0x58120,0x102f88,0x103aee,0x103b84})for(int mask=0;mask<2;mask++)for(long fl:new long[]{0,0x08000000L,0x10000000L,0x20000000L,0x40000000L,0x80000000L,INITIAL_FLAGS,0xf8000000L})for(int variant=0;variant<2;variant++){
    int arg=h==0x1e132?(variant==0?30:400):variant;
    fresh(false);entry(h,mask,fl);setup(h,arg);steps(stop(h,arg));long[]expected=regs();e.dispose();
    fresh(true);entry(h,mask,fl);setup(h,arg);int executed=steps(stop(h,arg));maximumEventSteps=Math.max(maximumEventSteps,executed);same(expected,"hook"+Long.toHexString(h));check(primask==mask,"incoming mask");check(deepestStack<=32,"local32");maximumEventStack=Math.max(maximumEventStack,(int)deepestStack);
    if(h==0x1bd6){check(state(12)==1&&word(STATE+128+16)==0x00140101&&word(STATE+128+20)==256,"actual tuple");check(word(SP)==0,"stackedarg");}
    if(h==0x1e132){check(state(17)==1000+arg&&state(18)==1000&&state(19)==arg&&state(20)==600/arg,"coherent operands");check((state(3)&1)==(arg==400?1:0),"q1only");}
    pass("ABI hook"+Long.toHexString(h)+" mask"+mask+" flags"+Long.toHexString(fl)+" variant"+variant);e.dispose();
   }
   for(int scenario=0;scenario<4;scenario++){
    fresh(true);put(0x2007ff80L+68,7);put(0x2007ff80L+56,9);put(0x2007ff80L+112,9);put(0x2007ff80L+60,0x00140101);
    if(scenario==3)invoke(0x1e104,0,0);
    invoke(0x1bd6,0,0);invoke(0x1bda,0,scenario==1?7:0);
    if(scenario!=1)invoke(0x103aee,0,scenario==2?0:1);
    if(scenario!=3)invoke(0x1e104,0,0);
    invoke(0x1e108,0,0);invoke(0x1e132,1,400);
    check((state(3)&1)==1,"full trace first fault");check(state(17)==1400&&state(18)==1000&&state(19)==400&&state(20)==1,"fulltrace operands");
    StringBuilder w=new StringBuilder();for(int k=0;k<128;k++)w.append(String.format("%08x",state(k)));
    JsonObject ob=new JsonObject();ob.addProperty("scenario",scenario);ob.addProperty("v",1);ob.addProperty("w",w.toString());snapshots.add(ob);
    pass("complete history scenario"+scenario);e.dispose();
   }
   // Boundary, freeze, overflow, ambiguity and epoch regressions execute final bytes.
   for(int d:new int[]{1,2,3,29,30,200,201,300,301,400,600,601,10000}){
    fresh(true);invoke(0x1e132,1,d);check(state(20)==600/d,"fullquotient");check((state(3)&1)==((d>=301&&d<=600)?1:0),"exactq1range");check(reg("r3")==600/d,"native quotient");pass("delta boundary"+d);e.dispose();
   }
   fresh(true);state(3,1);long[]frozen=new long[128];for(int i=0;i<128;i++)frozen[i]=state(i);for(long h:new long[]{0x1bd6,0x1bda,0x1e104,0x1e108,0x1e132,0x57fc4,0x58120,0x102f88,0x103aee,0x103b84}){entry(h,1,INITIAL_FLAGS);setup(h,h==0x1e132?400:1);for(int i=0;i<128;i++)state(i,frozen[i]);steps(stop(h,h==0x1e132?400:1));for(int i=0;i<128;i++)check(state(i)==frozen[i],"freezeimmutable");}pass("frozen observer immutable with native replay");e.dispose();
   fresh(true);for(int i=0;i<13;i++)invoke(0x1bd6,0,0);check(state(7)==12&&(state(3)&2)!=0&&(state(3)&4)!=0,"overrun overlap");pass("ring overrun and overlapping issue marked");e.dispose();
   fresh(true);invoke(0x57fc4,0,0);check(state(5)==2&&state(6)==2,"C3pending");invoke(0x102f88,0,0);check(state(6)==1,"C3commit");invoke(0x58120,0,0);check(state(5)==3&&state(6)==0,"C4epoch");pass("connection epoch pending commit disconnect");e.dispose();
   fresh(true);invoke(0x1e104,0,0);state(5,2);invoke(0x1e108,0,0);check((state(21)&256)==0,"query crossed epoch");invoke(0x1e132,1,400);check((state(3)&5)==5,"cross epoch fault inconclusive");pass("query epoch crossing invalidates evidence");e.dispose();
   for(int mask=0;mask<2;mask++){fresh(true);entry(symbols.get("observer_init")&~1,mask,INITIAL_FLAGS);e.writeRegister("r10",0x20070000L);long oldlr=reg("lr");steps(0x20a);check(state(0)==0x504d3636L&&state(1)==1&&state(2)==512&&state(3)==0,"initrecord");check(reg("sp")==SP&&reg("r10")==0x20070000L&&reg("lr")==oldlr&&flags()==INITIAL_FLAGS&&primask==mask,"initABI");check(deepestStack==0,"initstackless");pass("stackless init mask"+mask);e.dispose();}
   fresh(true);entry(0x19e8c,0,INITIAL_FLAGS);put(FP+20,4096);put(FP+24,INPUT);put(FP+28,7);put(FP+44,INPUT);String original="{\"x\":1}";e.writeMemory(a(INPUT),original.getBytes());bytePut(INPUT+original.length(),0);e.writeRegister("r0",original.length());boolean injected=false;int count=0;
   while(e.getExecutionAddress().getOffset()!=0x19e90){check(count++<20000,"snapshotbound");long pc=e.getExecutionAddress().getOffset();if(system(pc)){if(!injected&&primask==0&&reg("sp")<SP-32){state(0,0);state(4,999);injected=true;}continue;}e.setContextRegister(currentProgram.getRegister("TMode"),BigInteger.ONE);check(e.step(monitor),"readoutsnapshotstep");}
   check(injected,"postcopy external update injected");String snapText=new String(e.readMemory(a(INPUT),(int)reg("r0")));String snapWords=JsonParser.parseString(snapText).getAsJsonObject().getAsJsonObject("pm52_cmd66").get("w").getAsString();check(snapWords.startsWith("504d3636")&&Long.parseLong(snapWords.substring(32,40),16)==0,"coherent private snapshot unaffected by later update");pass("readout snapshot coherent after interrupt-unmask update");e.dispose();
   for(int v=0;v<8;v++){fresh(true);entry(0x19e8c,v==1?1:0,INITIAL_FLAGS);put(FP+20,v==2?4095:4096);put(FP+24,INPUT);put(FP+28,v==3?6:7);put(FP+44,INPUT);String json="{\"x\":1}";e.writeMemory(a(INPUT),json.getBytes());bytePut(INPUT+json.length(),0);e.writeRegister("r0",v==4?3500:json.length());if(v==5)bytePut(INPUT+json.length()-1,'x');if(v==6)state(0,0);if(v==7)put(FP+44,INPUT+1);steps(0x19e90);check(primask==(v==1?1:0)&&flags()==INITIAL_FLAGS&&reg("sp")==SP,"readoutABI");if(v==0){check(reg("r0")>1024,"readoutlen");String text=new String(e.readMemory(a(INPUT),(int)reg("r0")));check(JsonParser.parseString(text).getAsJsonObject().get("research_build").getAsString().equals("B2.1_OBS"),"research identifier");check(JsonParser.parseString(text).getAsJsonObject().getAsJsonObject("pm52_cmd66").get("w").getAsString().length()==1024,"readoutJSON");}else check(reg("r0")== (v==4?3500:json.length()),"readoutguard");check(deepestStack<=568,"readoutstack");for(int k:new int[]{1,4,5,6,7,8,9,10,11,12})check(reg("r"+k)==(k==7?FP:0x41000000L+k),"readout register preservation r"+k);check(reg("lr")== (RETURN|1)&&reg("r2")==reg("r0")&&reg("r3")==reg("r0"),"readout native replay LR/r2/r3");pass("readoutguard"+v);e.dispose();}
   for(int len:new int[]{2,3014,3015,4095}){
    fresh(true);entry(0x19e8c,0,INITIAL_FLAGS);put(FP+20,4096);put(FP+24,INPUT);put(FP+28,7);put(FP+44,INPUT);
    String json="{"+" ".repeat(len-2)+"}";e.writeMemory(a(INPUT),json.getBytes());bytePut(INPUT+len,0);e.writeRegister("r0",len);steps(0x19e90);
    check(reg("r0")== (len<=3014?len+1080:len),"exact capacity guard");check((e.readMemory(a(INPUT+reg("r0")),1)[0]&255)==0,"NUL capacity");check(deepestStack<=568&&reg("sp")==SP&&primask==0&&flags()==INITIAL_FLAGS,"capacity ABI");pass("research suffix capacity "+len);e.dispose();
   }
  }catch(Exception ex){error=ex.toString();printerr(error);}
  JsonObject j=new JsonObject();j.addProperty("status",error==null?"PASS":"FAIL");j.addProperty("passed",tests);j.addProperty("maximum_event_stack",maximumEventStack);j.addProperty("maximum_event_instructions",maximumEventSteps);j.addProperty("error",error);j.addProperty("application_sha256",sha(Path.of(p[2])));j.add("cases",cases);j.add("snapshots",snapshots);Files.writeString(Path.of(p[3]),new GsonBuilder().setPrettyPrinting().create().toJson(j));
 }
}

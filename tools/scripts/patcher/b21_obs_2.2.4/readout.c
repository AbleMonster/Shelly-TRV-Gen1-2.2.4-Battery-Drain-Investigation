typedef unsigned int u32;
typedef unsigned char u8;
#define R8(a) (*(volatile u8 *)(a))
#define R32(a) (*(volatile u32 *)(a))
#define S ((volatile u32 *)0x2007fd80u)
/* Called with interrupts masked. No native or observer state is changed.
 * The wrapper must restore registers/APSR and the original PRIMASK again. */
__attribute__((used,noinline))
u32 obs_export(u32 oldlen, u32 fp, u32 mask) {
    u32 snap[128];
    const u32 base=R32(fp+24), cap=R32(fp+20);
    static const char prefix[]=",\"research_build\":\"B2.1_OBS\",\"pm52_cmd66\":{\"v\":1,\"w\":\"";
    const u32 extra=(sizeof(prefix)-1)+1024+3;
    u32 ok=mask==0 && R32(fp+28)==7 && cap==4096 && R32(fp+44)==base;
    ok=ok && base>=0x20000000u && base<=0x20070000u-cap;
    ok=ok && oldlen>0 && oldlen<cap && extra<cap-oldlen;
    if(ok) ok=R8(base+oldlen)==0 && R8(base+oldlen-1)=='}'
              && S[0]==0x504d3636u && S[1]==1 && S[2]==512;
    if(ok) for(u32 i=0;i<128;i++) snap[i]=S[i];
    __asm__ volatile("msr primask,%0"::"r"(mask):"memory");
    if(!ok) return oldlen;
    u8 *out=(u8 *)(base+oldlen-1);
    for(u32 i=0;i<sizeof(prefix)-1;i++) *out++=(u8)prefix[i];
    for(u32 i=0;i<128;i++) for(int n=28;n>=0;n-=4) {
        u32 d=(snap[i]>>n)&15; *out++=(u8)(d<10?'0'+d:'a'+d-10);
    }
    *out++='"'; *out++='}'; *out++='}'; *out=0;
    return (u32)out-base;
}

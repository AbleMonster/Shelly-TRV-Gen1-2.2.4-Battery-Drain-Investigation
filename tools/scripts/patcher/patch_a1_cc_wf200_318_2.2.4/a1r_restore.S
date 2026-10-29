/* A1R authoritative correction: temporary H180 origins preserve restore intent.
 * r1 is normalized caller return PC; LR holds native A base. r2 is dead at
 * the replaced block and overwritten at native10389e before any live use.
 * No calls, frame, PRIMASK operation, mutable state or native wait.
 * Exact addresses are asserted by the construction/independent verifier.
 */
.syntax unified
.cpu cortex-m4
.thumb
.text
.org 0x103878,0xff
.global a1r_hook
 a1r_hook:
 b.w .La1r_origin
 nop
.org 0x10387e,0xff
native_after_saved:
.org 0x1046dc,0xff
.global a1r_restore_origin
.type a1r_restore_origin,%function
.thumb_func
a1r_restore_origin:
.La1r_origin:
 ldr r2,=0x17498 /* physical button */
 cmp r1,r2
 beq .Ltemporary
 ldr r2,=0x1b65e /* HTTP psovrd */
 cmp r1,r2
 beq .Ltemporary
 ldr r2,=0x6d826 /* Cloud psovrd */
 cmp r1,r2
 beq .Ltemporary
 ldr r2,=0x19d78 /* settings_sta serialization */
 cmp r1,r2
 beq .Ltemporary
 ldr r2,=0x1cfb6 /* OTA launcher */
 cmp r1,r2
 beq .Ltemporary
 /* Existing generic persistent Active semantics. Recovery never reaches
  * this block; its old-A1 no-op remains at103838..103844. */
 movs r0,#1
 strb.w r0,[lr,#4]
.Ltemporary:
 b.w native_after_saved
.size a1r_restore_origin,.-a1r_restore_origin
.balign 4,0xff
.ltorg
.global a1r_program_end
a1r_program_end:

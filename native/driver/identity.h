/* Portable identity response builder shared by driver and native C tests.
 * Synthetic identity, NOT genuine firmware. Checksum remains zero by design.
 * Format: https://docs.elgato.com/streamdeck/hid/general/
 */
#ifndef D6_IDENTITY_H
#define D6_IDENTITY_H
static int D6Identity(unsigned char id, unsigned char *out, unsigned long capacity) {
    unsigned long i;
    static const unsigned char serial[12] = "D6VIRTUAL001";
    static const unsigned char firmware[8] = "1.00.000";
    if (!out || capacity < 32) return -1;
    for (i=0; i<capacity; ++i) out[i]=0;
    out[0]=id;
    if (id==6) {
        out[1]=12;
        for(i=0;i<12;++i) out[i+2]=serial[i];
    } else if(id==5) {
        out[1]=12;
        for(i=0;i<8;++i) out[i+6]=firmware[i];
    } else return 0;
    return 1;
}
#endif

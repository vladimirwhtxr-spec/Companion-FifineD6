#include <assert.h>
#include <string.h>
#include "driver/identity.h"
int main(void) {
    unsigned char out[40];
    memset(out,0xcc,sizeof(out));
    assert(D6Identity(6,out,32)==1);
    assert(out[0]==6 && out[1]==12);
    assert(memcmp(out+2,"D6VIRTUAL001",12)==0);
    for(int i=14;i<32;++i) assert(out[i]==0);
    assert(out[32]==0xcc);
    assert(D6Identity(5,out,32)==1);
    assert(out[1]==12 && memcmp(out+6,"1.00.000",8)==0);
    for(int i=2;i<6;++i) assert(out[i]==0);
    assert(D6Identity(8,out,32)==0);
    out[0]=0xcc;
    assert(D6Identity(6,out,31)==-1 && out[0]==0xcc);
    assert(D6Identity(6,0,32)==-1);
    return 0;
}

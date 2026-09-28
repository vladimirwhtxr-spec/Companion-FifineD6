import io
import unittest
from PIL import Image
from streamdeck_protocol import ImageAssembler, key_report, to_d6
from d6_usb import reports


def packets(data,key=0):
    for page,start in enumerate(range(0,len(data),1016)):
        part=data[start:start+1016]
        yield (bytes([2,7,key,int(start+len(part)==len(data))])+
               len(part).to_bytes(2,'little')+page.to_bytes(2,'little')+part).ljust(1024,b'\0')


class ProtocolTests(unittest.TestCase):
    def test_reassembly_interleaved(self):
        a=ImageAssembler()
        one=b'\xff\xd8'+b'a'*2400+b'\xff\xd9'
        two=b'\xff\xd8'+b'b'*1200+b'\xff\xd9'
        x,y=list(packets(one,0)),list(packets(two,14))
        self.assertIsNone(a.feed(x[0]))
        self.assertIsNone(a.feed(y[0]))
        self.assertIsNone(a.feed(x[1]))
        self.assertEqual(a.feed(y[1]),(15,two))
        self.assertEqual(a.feed(x[2]),(1,one))
        self.assertFalse(a.pending)

    def test_missing_page_and_bounds(self):
        a=ImageAssembler()
        p=list(packets(b'\xff\xd8'+b'a'*3000+b'\xff\xd9'))
        a.feed(p[0])
        with self.assertRaises(ValueError): a.feed(p[2])
        self.assertFalse(a.pending)
        bad=bytearray(p[0]); bad[4:6]=(1017).to_bytes(2,'little')
        with self.assertRaises(ValueError): a.feed(bad)
        with self.assertRaises(ValueError): a.feed(p[0][:8])
        for page in range(64):
            r=bytearray(p[0]); r[6:8]=page.to_bytes(2,'little')
            a.feed(r)
        r[6:8]=(64).to_bytes(2,'little')
        with self.assertRaises(ValueError): a.feed(r)

    def test_orientation_size_and_d6_framing(self):
        im=Image.new('RGB',(72,72),'blue')
        for x in range(36):
            for y in range(36): im.putpixel((x,y),(255,0,0))
        # This is the already rotated Elgato wire image; both native transforms cancel.
        b=io.BytesIO(); im.save(b,format='JPEG',quality=95)
        result=to_d6(b.getvalue())
        decoded=Image.open(io.BytesIO(result))
        self.assertEqual(decoded.size,(112,112))
        self.assertGreater(decoded.getpixel((10,10))[0],200)
        self.assertGreater(decoded.getpixel((100,100))[2],200)
        r=list(reports(result,5))
        self.assertTrue(all(len(x)==1024 for x in r))
        self.assertEqual(r[0][10:13],len(result).to_bytes(2,'big')+b'\x05')
        self.assertEqual(b''.join(r[1:-1])[:len(result)],result)

    def test_key_edges(self):
        states=[0]*15
        states[14]=1
        self.assertEqual(key_report(states),b'\x01\x00\x0f\x00'+bytes(14)+b'\x01')
        states[14]=0
        self.assertEqual(key_report(states)[4:],bytes(15))
        with self.assertRaises(ValueError): key_report([0]*14)


if __name__=='__main__': unittest.main()

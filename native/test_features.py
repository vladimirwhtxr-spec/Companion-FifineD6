import io
import unittest
from PIL import Image
from streamdeck_protocol import feature_frames

class FeatureTests(unittest.TestCase):
    def test_fill_all(self):
        frames=feature_frames(bytes([3,5,200,10,30]).ljust(32,b'\0'))
        self.assertEqual([k for k,_ in frames],list(range(1,16)))
        pixel=Image.open(io.BytesIO(frames[0][1])).getpixel((50,50))
        self.assertTrue(all(abs(a-b)<5 for a,b in zip(pixel,(200,10,30))))

    def test_fill_single_and_logo_placeholder(self):
        frames=feature_frames(bytes([3,6,14,0,255,0]).ljust(32,b'\0'))
        self.assertEqual([k for k,_ in frames],[15])
        frames=feature_frames(b'\x03\x02'.ljust(32,b'\0'))
        self.assertEqual(Image.open(io.BytesIO(frames[0][1])).getpixel((50,50)),(0,0,0))

    def test_invalid_feature_and_brightness(self):
        for raw in [bytes([3,6,15]),bytes([3,8,101]),bytes([3,255])]:
            with self.assertRaises(ValueError): feature_frames(raw.ljust(32,b'\0'))
        with self.assertRaises(ValueError): feature_frames(b'\x03\x05')
        self.assertEqual(feature_frames(bytes([3,8,60]).ljust(32,b'\0')),[])

if __name__=='__main__': unittest.main()

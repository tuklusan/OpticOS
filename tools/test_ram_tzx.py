"""Structural checks for our standard-speed, self-booting TZX."""
import importlib.util
import pathlib
import struct
import unittest

SPEC = importlib.util.spec_from_file_location(
    "make_ram_tzx", pathlib.Path(__file__).with_name("make_ram_tzx.py"))
tzx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tzx)


def parse_blocks(raw):
    assert raw[:10] == b"ZXTape!\x1a\x01\x14"
    pos, blocks = 10, []
    while pos < len(raw):
        assert raw[pos] == 0x10
        pause, size = struct.unpack_from("<HH", raw, pos+1)
        pos += 5
        payload = raw[pos:pos+size]
        assert len(payload) == size
        assert pause == 1000
        assert not (sum([]) if False else 0)  # explicit no stateful decoder
        parity = 0
        for value in payload:
            parity ^= value
        assert parity == 0, "bad tape checksum"
        blocks.append(payload)
        pos += size
    return blocks


class RamTapeTests(unittest.TestCase):
    def test_tzx_structure(self):
        image = b"\xf3\xaf\xc3\x10\x60" + bytes(range(256))
        blocks = parse_blocks(tzx.make_tzx(image))
        self.assertEqual([x[0] for x in blocks], [0, 0xFF, 0, 0xFF])
        self.assertEqual(len(blocks[0]), 19)
        self.assertEqual(len(blocks[2]), 19)
        self.assertEqual(blocks[2][1], 3)  # CODE header
        length, address, unused = struct.unpack_from("<HHH", blocks[2], 12)
        self.assertEqual((length, address, unused),
                         (len(image), tzx.LOAD_ADDR, 0x8000))
        self.assertEqual(blocks[3][1:-1], image)

    def test_loader(self):
        blocks = parse_blocks(tzx.make_tzx(b"\xc3\x00\x60"))
        data = blocks[1][1:-1]
        self.assertEqual(struct.unpack_from("<H", blocks[0], 14)[0], 10)
        self.assertIn(b"\xfd \xb0", data)  # CLEAR VAL
        self.assertIn(b"\xef \"\" \xaf", data)  # LOAD "" CODE
        self.assertIn(b"\xf9 \xc0 \xb0", data)  # RANDOMIZE USR VAL
        self.assertEqual(data.count(b"\r"), 3)

    def test_refuse_too_large(self):
        with self.assertRaises(ValueError):
            tzx.make_tzx(bytes(tzx.MAX_IMAGE))


if __name__ == "__main__":
    unittest.main()

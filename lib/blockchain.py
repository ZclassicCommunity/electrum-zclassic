# Electrum - lightweight ZClassic client
# Copyright (C) 2012 thomasv@ecdsa.org
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import os
import threading
from time import sleep

from . import util
from . import bitcoin
from . import constants
from .bitcoin import *

HDR_LEN = 1487
HDR_EH_192_7_LEN = 543
CHUNK_LEN = 100
BUBBLES_ACTIVATION_HEIGHT = 585318
DIFFADJ_ACTIVATION_HEIGHT = 585322

MAX_TARGET = 0x0007FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
POW_AVERAGING_WINDOW = 17
POW_MEDIAN_BLOCK_SPAN = 11
POW_MAX_ADJUST_DOWN = 32
POW_MAX_ADJUST_UP = 16
POW_DAMPING_FACTOR = 4
POW_TARGET_SPACING = 150

TARGET_CALC_BLOCKS = POW_AVERAGING_WINDOW + POW_MEDIAN_BLOCK_SPAN

AVERAGING_WINDOW_TIMESPAN = POW_AVERAGING_WINDOW * POW_TARGET_SPACING

MIN_ACTUAL_TIMESPAN = AVERAGING_WINDOW_TIMESPAN * \
    (100 - POW_MAX_ADJUST_UP) // 100

MAX_ACTUAL_TIMESPAN = AVERAGING_WINDOW_TIMESPAN * \
    (100 + POW_MAX_ADJUST_DOWN) // 100


def is_post_equihash_fork(height):
    return height >= BUBBLES_ACTIVATION_HEIGHT

def get_header_size(height):
    if is_post_equihash_fork(height):
        return HDR_EH_192_7_LEN
    return HDR_LEN

def serialize_header(res):
    s = int_to_hex(res.get('version'), 4) \
        + rev_hex(res.get('prev_block_hash')) \
        + rev_hex(res.get('merkle_root')) \
        + rev_hex(res.get('reserved_hash')) \
        + int_to_hex(int(res.get('timestamp')), 4) \
        + int_to_hex(int(res.get('bits')), 4) \
        + rev_hex(res.get('nonce')) \
        + rev_hex(res.get('sol_size')) \
        + rev_hex(res.get('solution'))
    return s

def deserialize_header(s, height):
    if not s:
        raise Exception('Invalid header: {}'.format(s))
    if len(s) != get_header_size(height):
        raise Exception('Invalid header length: {}'.format(len(s)))
    hex_to_int = lambda s: int('0x' + bh2u(s[::-1]), 16)
    h = {}
    h['version'] = hex_to_int(s[0:4])
    h['prev_block_hash'] = hash_encode(s[4:36])
    h['merkle_root'] = hash_encode(s[36:68])
    h['reserved_hash'] = hash_encode(s[68:100])
    h['timestamp'] = hex_to_int(s[100:104])
    h['bits'] = hex_to_int(s[104:108])
    h['nonce'] = hash_encode(s[108:140])
    h['sol_size'] = hash_encode(s[140:143])
    h['solution'] = hash_encode(s[143:])
    h['block_height'] = height
    return h

def hash_header(header):
    if header is None:
        return '0' * 64
    if header.get('prev_block_hash') is None:
        header['prev_block_hash'] = '00'*32
    return hash_encode(Hash(bfh(serialize_header(header))))


blockchains = {}

def read_blockchains(config):
    blockchains[0] = Blockchain(config, 0, None)
    fdir = os.path.join(util.get_headers_dir(config), 'forks')
    if not os.path.exists(fdir):
        os.mkdir(fdir)
    l = filter(lambda x: x.startswith('fork_'), os.listdir(fdir))
    l = sorted(l, key = lambda x: int(x.split('_')[1]))
    for filename in l:
        checkpoint = int(filename.split('_')[2])
        parent_id = int(filename.split('_')[1])
        b = Blockchain(config, checkpoint, parent_id)
        h = b.read_header(b.checkpoint)
        if b.parent().can_connect(h, check_height=False):
            blockchains[b.checkpoint] = b
        else:
            util.print_error("cannot connect", filename)
    return blockchains

def check_header(header):
    if type(header) is not dict:
        return False
    for b in blockchains.values():
        if b.check_header(header):
            return b
    return False

def can_connect(header):
    for b in blockchains.values():
        if b.can_connect(header):
            return b
    return False


class Blockchain(util.PrintError):
    """
    Manages blockchain headers and their verification
    """

    def __init__(self, config, checkpoint, parent_id):
        self.config = config
        self.catch_up = None # interface catching up
        self.checkpoint = checkpoint
        self.checkpoints = constants.net.CHECKPOINTS
        self.parent_id = parent_id
        self.lock = threading.Lock()
        with self.lock:
            self.update_size(0)

    def parent(self):
        return blockchains[self.parent_id]

    def get_max_child(self):
        children = list(filter(lambda y: y.parent_id==self.checkpoint, blockchains.values()))
        return max([x.checkpoint for x in children]) if children else None

    def get_checkpoint(self):
        mc = self.get_max_child()
        return mc if mc is not None else self.checkpoint

    def get_branch_size(self):
        return self.height() - self.get_checkpoint() + 1

    def get_name(self):
        return self.get_hash(self.get_checkpoint()).lstrip('00')[0:10]

    def check_header(self, header):
        header_hash = hash_header(header)
        height = header.get('block_height')
        return header_hash == self.get_hash(height)

    def fork(parent, header):
        checkpoint = header.get('block_height')
        self = Blockchain(parent.config, checkpoint, parent.checkpoint)
        open(self.path(), 'w+').close()
        self.save_header(header)
        return self

    def height(self):
        return self.checkpoint + self.size() - 1

    def size(self):
        with self.lock:
            return self._size

    def update_size(self, height):
        p = self.path()
        if os.path.exists(p):
            with open(p, 'rb') as f:
                size = f.seek(0, 2)
            self._size = self.calculate_size(height, size)
        else:
            self._size = 0

    def calculate_size(self, checkpoint, size_in_bytes):
        size_before_fork = 0
        size_after_fork = 0

        if not is_post_equihash_fork(checkpoint):
            size_before_fork = size_in_bytes//HDR_LEN
            if is_post_equihash_fork(size_before_fork):
                size_before_fork = BUBBLES_ACTIVATION_HEIGHT
                checkpoint = BUBBLES_ACTIVATION_HEIGHT
                size_in_bytes -= size_before_fork * HDR_LEN
        else:
            size_before_fork = BUBBLES_ACTIVATION_HEIGHT
            size_in_bytes -= size_before_fork * HDR_LEN

        if is_post_equihash_fork(checkpoint):
            size_after_fork = size_in_bytes//HDR_EH_192_7_LEN

        return size_before_fork + size_after_fork

    def verify_header(self, header, prev_hash, target):
        _hash = hash_header(header)
        if prev_hash != header.get('prev_block_hash'):
            raise Exception("prev hash mismatch: %s vs %s" % (prev_hash, header.get('prev_block_hash')))
        if constants.net.TESTNET:
            return
        bits = self.target_to_bits(target)
        height = header.get('block_height')
        if height >= DIFFADJ_ACTIVATION_HEIGHT and height < DIFFADJ_ACTIVATION_HEIGHT + POW_AVERAGING_WINDOW:
            valid_bits = [
                0x1f07ffff, 0x1e0ffffe, 0x1e0ffffe, 0x1f07ffff, 0x1f014087, 0x1f01596b,
                0x1f01743d, 0x1f019124, 0x1f01b049, 0x1f01d1da, 0x1f01f606, 0x1f021d01,
                0x1f024703, 0x1f027448, 0x1f02a510, 0x1f02d9a3, 0x1f03124a,
                ]
            bits = valid_bits[height%DIFFADJ_ACTIVATION_HEIGHT]
            target = self.bits_to_target(bits)
        if bits != header.get('bits'):
            raise Exception("bits mismatch: %s vs %s" % (bits, header.get('bits')))
        if int('0x' + _hash, 16) > target:
            raise Exception("insufficient proof of work: %s vs target %s" % (int('0x' + _hash, 16), target))

    def verify_chunk(self, height, data):
        size = len(data)
        prev_hash = self.get_hash(height-1)
        chunk_headers = {'empty': True}
        offset = 0
        i = 0
        while offset < size:
            header_size = get_header_size(height)
            raw_header = data[offset:offset+header_size]
            header = deserialize_header(raw_header, height)
            target = self.get_target(height, chunk_headers)
            self.verify_header(header, prev_hash, target)

            chunk_headers[height] = header
            if i == 0:
                chunk_headers['min_height'] = height
                chunk_headers['empty'] = False
            chunk_headers['max_height'] = height
            prev_hash = hash_header(header)
            offset += header_size
            height += 1
            i += 1
            sleep(0.001)

    def path(self):
        d = util.get_headers_dir(self.config)
        filename = 'blockchain_headers' if self.parent_id is None else os.path.join('forks', 'fork_%d_%d'%(self.parent_id, self.checkpoint))
        return os.path.join(d, filename)

    def save_chunk(self, height, chunk):
        delta = height - self.checkpoint

        if delta < 0:
            chunk = chunk[-delta:]
            height = self.checkpoint

        offset = self.get_offset(self.checkpoint, height)
        truncate = (height / CHUNK_LEN) >= len(self.checkpoints)
        self.write(chunk, offset, truncate)
        self.swap_with_parent()

    def swap_with_parent(self):
        if self.parent_id is None:
            return
        parent_branch_size = self.parent().height() - self.checkpoint + 1
        if parent_branch_size >= self.size():
            return
        self.print_error("swap", self.checkpoint, self.parent_id)
        parent_id = self.parent_id
        checkpoint = self.checkpoint
        parent = self.parent()
        with open(self.path(), 'rb') as f:
            my_data = f.read()
        offset = self.get_offset(parent.checkpoint, checkpoint)
        with open(parent.path(), 'rb') as f:
            f.seek(offset)
            parent_data = f.read()
        self.write(parent_data, 0)
        parent.write(my_data, offset)
        # store file path
        for b in blockchains.values():
            b.old_path = b.path()
        # swap parameters
        self.parent_id = parent.parent_id; parent.parent_id = parent_id
        self.checkpoint = parent.checkpoint; parent.checkpoint = checkpoint
        self._size = parent._size; parent._size = parent_branch_size
        # move files
        for b in blockchains.values():
            if b in [self, parent]: continue
            if b.old_path != b.path():
                self.print_error("renaming", b.old_path, b.path())
                os.rename(b.old_path, b.path())
        # update pointers
        blockchains[self.checkpoint] = self
        blockchains[parent.checkpoint] = parent

    def write(self, data, offset, truncate=True):
        filename = self.path()
        current_offset = self.get_offset(self.checkpoint, self.size())

        with self.lock:
            with open(filename, 'rb+') as f:
                if truncate and offset != current_offset:
                    f.seek(offset)
                    f.truncate()
                f.seek(offset)
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        self.update_size(self.size())

    def save_header(self, header):
        height = header.get('block_height')
        delta = height - self.checkpoint
        data = bfh(serialize_header(header))
        offset = self.get_offset(self.checkpoint, height)
        header_size = get_header_size(height)

        assert delta == self.size()
        assert len(data) == header_size
        self.write(data, offset)
        self.swap_with_parent()

    def read_header(self, height):
        assert self.parent_id != self.checkpoint
        if height < 0:
            return
        if height < self.checkpoint:
            return self.parent().read_header(height)
        if height > self.height():
            return
        offset = self.get_offset(self.checkpoint, height)
        header_size = get_header_size(height)
        name = self.path()
        if os.path.exists(name):
            with open(name, 'rb') as f:
                f.seek(offset)
                h = f.read(header_size)
                if len(h) < header_size:
                    raise Exception('Expected to read a full header. This was only {} bytes'.format(len(h)))
        elif not os.path.exists(util.get_headers_dir(self.config)):
            raise Exception('Electrum datadir does not exist. Was it deleted while running?')
        else:
            raise Exception('Cannot find headers file but datadir is there. Should be at {}'.format(name))
        if h == bytes([0])*header_size:
            return None
        return deserialize_header(h, height)

    def get_hash(self, height):
        if height == -1:
            return '0000000000000000000000000000000000000000000000000000000000000000'
        elif height == 0:
            return constants.net.GENESIS
        elif height < len(self.checkpoints) * CHUNK_LEN - TARGET_CALC_BLOCKS:
            assert (height+1) % CHUNK_LEN == 0, height
            index = height // CHUNK_LEN
            h, t, extra_headers = self.checkpoints[index]
            return h
        else:
            return hash_header(self.read_header(height))

    def get_median_time(self, height, chunk_headers=None):
        if chunk_headers is None or chunk_headers['empty']:
            chunk_empty = True
        else:
            chunk_empty = False
            min_height = chunk_headers['min_height']
            max_height = chunk_headers['max_height']

        height_range = range(max(0, height - POW_MEDIAN_BLOCK_SPAN),
                             max(1, height))
        median = []
        for h in height_range:
            header = self.read_header(h)
            if not header and not chunk_empty \
                and min_height <= h <= max_height:
                    header = chunk_headers[h]
            if not header:
                raise Exception("Can not read header at height %s" % h)
            median.append(header.get('timestamp'))

        median.sort()
        return median[len(median)//2];

    def get_target(self, height, chunk_headers=None):
        if chunk_headers is None or chunk_headers['empty']:
            chunk_empty = True
        else:
            chunk_empty = False
            min_height = chunk_headers['min_height']
            max_height = chunk_headers['max_height']

        if height <= POW_AVERAGING_WINDOW:
            return MAX_TARGET

        height_range = range(max(0, height - POW_AVERAGING_WINDOW),
                             max(1, height))
        mean_target = 0
        for h in height_range:
            header = self.read_header(h)
            if not header and not chunk_empty \
                and min_height <= h <= max_height:
                    header = chunk_headers[h]
            if not header:
                raise Exception("Can not read header at height %s" % h)
            mean_target += self.bits_to_target(header.get('bits'))
        mean_target //= POW_AVERAGING_WINDOW

        actual_timespan = self.get_median_time(height, chunk_headers) - \
            self.get_median_time(height - POW_AVERAGING_WINDOW, chunk_headers)
        actual_timespan = AVERAGING_WINDOW_TIMESPAN + \
            int((actual_timespan - AVERAGING_WINDOW_TIMESPAN) / \
                POW_DAMPING_FACTOR)
        if actual_timespan < MIN_ACTUAL_TIMESPAN:
            actual_timespan = MIN_ACTUAL_TIMESPAN
        elif actual_timespan > MAX_ACTUAL_TIMESPAN:
            actual_timespan = MAX_ACTUAL_TIMESPAN

        next_target = mean_target // AVERAGING_WINDOW_TIMESPAN * actual_timespan

        if next_target > MAX_TARGET:
            next_target = MAX_TARGET

        return next_target

    def bits_to_target(self, bits):
        bitsN = (bits >> 24) & 0xff
        if not (bitsN >= 0x03 and bitsN <= 0x1f):
            if not constants.net.TESTNET:
                raise Exception("First part of bits should be in [0x03, 0x1f]")
        bitsBase = bits & 0xffffff
        if not (bitsBase >= 0x8000 and bitsBase <= 0x7fffff):
            raise Exception("Second part of bits should be in [0x8000, 0x7fffff]")
        return bitsBase << (8 * (bitsN-3))

    def target_to_bits(self, target):
        c = ("%064x" % target)[2:]
        while c[:2] == '00' and len(c) > 6:
            c = c[2:]
        bitsN, bitsBase = len(c) // 2, int('0x' + c[:6], 16)
        if bitsBase >= 0x800000:
            bitsN += 1
            bitsBase >>= 8
        return bitsN << 24 | bitsBase

    def can_connect(self, header, check_height=True):
        if header is None:
            return False
        height = header['block_height']
        if check_height and self.height() != height - 1:
            #self.print_error("cannot connect at height", height)
            return False
        if height == 0:
            return hash_header(header) == constants.net.GENESIS
        try:
            prev_hash = self.get_hash(height - 1)
        except:
            return False
        if prev_hash != header.get('prev_block_hash'):
            return False
        target = self.get_target(height)
        try:
            self.verify_header(header, prev_hash, target)
        except BaseException as e:
            return False
        return True

    def connect_chunk(self, idx, hexdata):
        try:
            data = bfh(hexdata)
            self.verify_chunk(idx * CHUNK_LEN, data)
            # self.print_error("validated chunk %d" % idx)
            self.save_chunk(idx * CHUNK_LEN, data)
            return True
        except BaseException as e:
            self.print_error('verify_chunk %d failed'%idx, str(e))
            return False

    def get_checkpoints(self):
        # for each chunk, store the hash of the last block and the target after the chunk
        cp = []
        n = self.height() // CHUNK_LEN
        for index in range(n):
            height = (index + 1) * CHUNK_LEN - 1
            h = self.get_hash(height)
            target = self.get_target(height)
            if len(h.strip('0')) == 0:
                raise Exception('%s file has not enough data.' % self.path())
            extra_headers = []
            if os.path.exists(self.path()):
                with open(self.path(), 'rb') as f:
                    lower_header = height - TARGET_CALC_BLOCKS
                    for height in range(height, lower_header-1, -1):
                        f.seek(height*get_header_size(height))
                        hd = f.read(get_header_size(height))
                        if len(hd) < get_header_size(height):
                            raise Exception(
                                'Expected to read a full header.'
                                ' This was only {} bytes'.format(len(hd)))
                        extra_headers.append((height, bh2u(hd)))
            cp.append((h, target, extra_headers))
        return cp

    def get_offset(self, checkpoint, height):
        offset_before_fork = 0
        offset_after_fork = 0

        if not is_post_equihash_fork(height):
            offset_before_fork = height - checkpoint
        else:
            offset_before_fork = BUBBLES_ACTIVATION_HEIGHT

        if is_post_equihash_fork(height):
            offset_after_fork = height - max(checkpoint, BUBBLES_ACTIVATION_HEIGHT)

        offset = (offset_before_fork * HDR_LEN) + (offset_after_fork * HDR_EH_192_7_LEN)
        return offset

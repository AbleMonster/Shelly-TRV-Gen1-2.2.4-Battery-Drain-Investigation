#!/usr/bin/env python3
import unittest
from decode import decode

def fixture():
    s=[0]*128
    s[:9]=[0x504d3636,1,512,1,11,1,1,4,4]
    s[12:15]=[1,1,0]
    s[16:24]=[0,700,100,600,1,0x301,1,10]
    s[24:30]=[5,6,6,0,0x00140101,0]
    for i,r in enumerate(([1,100,1,1,0x00140101,0x100,5,88],
                          [2,101,1,2,1,0,5,0],
                          [3,102,1,6,1,5,6,1],
                          [11,103,1,9,700,100,600,1])):
        s[32+8*i:40+8*i]=r
    return s

def doc(s): return {'pm52_cmd66':{'v':1,'w':''.join(f'{x:08x}' for x in s)}}

class DecoderTests(unittest.TestCase):
    def test_case_a(self): self.assertTrue(decode(doc(fixture()))['classification'].startswith('CASE A'))
    def test_physical_completedgen_not_required(self):
        s=fixture(); s[27]=999
        self.assertTrue(decode(doc(s))['classification'].startswith('CASE A'))
    def test_case_b_failure(self):
        s=fixture();s[14]=7;s[45]=7
        self.assertTrue(decode(doc(s))['classification'].startswith('CASE B'))
    def test_case_b_rejection(self):
        s=fixture();s[52]=0
        self.assertTrue(decode(doc(s))['classification'].startswith('CASE B'))
    def test_fail_closed_mutations(self):
        for index,value in ((3,0),(3,3),(3,5),(3,9),(3,17),(5,0),(6,2),(12,9),
                            (13,2),(16,7),(19,0),(19,300),(20,2),(21,1),(22,2),
                            (24,6),(25,7),(26,7),(28,0),(29,1),(37,0),(52,2),
                            (54,7),(9,1)):
            s=fixture();s[index]=value
            self.assertTrue(decode(doc(s))['classification'].startswith('CASE C'),(index,value))
    def test_pm_completion_after_query_is_inconclusive(self):
        for query_seq in (1,2,3):
            s=fixture();s[23]=query_seq
            self.assertTrue(decode(doc(s))['classification'].startswith('CASE C'))
    def test_missing_or_late_query_is_inconclusive(self):
        for query_seq in (0,11,12):
            s=fixture();s[23]=query_seq
            self.assertTrue(decode(doc(s))['classification'].startswith('CASE C'))
    def test_reject_bad_shape(self):
        for d in ({'pm52_cmd66':{'v':1,'w':'0'*1023}},doc([0]*128)):
            with self.assertRaises(ValueError): decode(d)

if __name__=='__main__': unittest.main()

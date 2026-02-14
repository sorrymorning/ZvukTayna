import wave
import os
import numpy as np
from typing import Tuple, Optional
from libs.lsb import LSBCodingStego
from libs.phase import PhaseCodingStego


import argparse

methods = {
    "lsb": LSBCodingStego,
    "phase": PhaseCodingStego
}



def main():
    parser = argparse.ArgumentParser(prog="stego")
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode_parser = subparsers.add_parser("encode")
    encode_parser.add_argument("--infile", required=True)
    encode_parser.add_argument("--outfile", required=True)
    encode_parser.add_argument("--method", choices=["lsb", "phase"], required=True)
    encode_parser.add_argument("--msg", required=True)

    decode_parser = subparsers.add_parser("decode")
    decode_parser.add_argument("--infile", required=True)
    encode_parser.add_argument("--method", choices=["lsb", "phase"], required=True)

    args = parser.parse_args()

    if args.command == "encode":
        method = methods[args.method]()
        result,info = method.encode(args.infile,args.outfile,args.msg)
        print(info)

    elif args.command == "decode":
        method = methods[args.method]()
        result,info = method.decode(args.infile)
        print(info)

if __name__ == "__main__":
    main()

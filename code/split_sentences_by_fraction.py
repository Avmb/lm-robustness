#! /usr/bin/env python3

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description='Split sentences by fraction of words')
    parser.add_argument('-l', '--left-output-file', type=str, required=True,
                        help='output file for left part of the sentences')
    parser.add_argument('-r', '--right-output-file', type=str, required=True,
                        help='output file for right part of the sentences')
    parser.add_argument('--ratio', type=float, default=0.5,
                         help='word ratio')
    parser.add_argument('--skip-short-left', type=int, default=2,
                         help='skip sentences where the left part is shorter than this many words (default: 2)')
    args = parser.parse_args()

    with open(args.left_output_file, "w") as lf:
        with open(args.right_output_file, "w") as rf:
            for line in sys.stdin:
                tokens = line.strip().split()
                idx = round(len(tokens) * args.ratio)
                left_tokens = tokens[:idx]
                right_tokens = tokens[idx:]
                if len(left_tokens) < args.skip_short_left:
                    continue
                print(" ".join(left_tokens), file=lf)
                print(" ".join(right_tokens), file=rf)

if __name__ == '__main__':
    main()

# lm-robustness
Robust recurrent language model with Random Network Distillation

Based on code from https://github.com/bzhangGo/lrn

Baseline training hyperparameters:
- training
  ```
  #! /bin/bash

  export CUDA_VISIBLE_DEVICES=0

  # for PTB
  python3 main.py --data path-of/penn --dropouti 0.4 --dropoutl 0.29 --dropouth 0.225 --seed 28 --batch_size 12 --lr 10.0 --epoch 1000 --nhid 960 --nhidlast 620 --emsize 280 --n_experts 15 --save PTB --single_gpu --model lrn
  # for WT2
  python3 main.py --epochs 1000 --data path-of/wikitext-2 --save WT2 --dropouth 0.2 --seed 1882 --n_experts 15 --nhid 1150 --nhidlast 650 --emsize 300 --batch_size 15 --lr 15.0 --dropoutl 0.29 --small_batch_size 5 --max_seq_len_delta 20 --dropouti 0.55 --single_gpu --model lrn  
  ```

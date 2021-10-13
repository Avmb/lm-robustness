import argparse
import os, sys
import time
import math
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

import gc

import data
import model

from utils import batchify, get_batch, eval_batchify, get_eval_batch, repackage_hidden, create_exp_dir, save_checkpoint

parser = argparse.ArgumentParser(description='PyTorch PennTreeBank/WikiText2 RNN/LSTM Language Model')
parser.add_argument('--test_data', type=str, default='./penn/',
                    help='location of the test data corpus')
parser.add_argument('--model', type=str, default='LSTM',
                    help='type of recurrent net (RNN_TANH, RNN_RELU, LSTM, GRU, SRU)')
parser.add_argument('--emsize', type=int, default=400,
                    help='size of word embeddings')
parser.add_argument('--nhid', type=int, default=1150,
                    help='number of hidden units per layer')
parser.add_argument('--nhidlast', type=int, default=-1,
                    help='number of hidden units for the last rnn layer')
parser.add_argument('--nlayers', type=int, default=3,
                    help='number of layers')
parser.add_argument('--lr', type=float, default=30,
                    help='initial learning rate')
parser.add_argument('--clip', type=float, default=0.25,
                    help='gradient clipping')
parser.add_argument('--epochs', type=int, default=8000,
                    help='upper epoch limit')
parser.add_argument('--batch_size', type=int, default=20, metavar='N',
                    help='batch size')
parser.add_argument('--bptt', type=int, default=70,
                    help='sequence length')
parser.add_argument('--dropout', type=float, default=0.4,
                    help='dropout applied to layers (0 = no dropout)')
parser.add_argument('--dropouth', type=float, default=0.3,
                    help='dropout for rnn layers (0 = no dropout)')
parser.add_argument('--dropouti', type=float, default=0.65,
                    help='dropout for input embedding layers (0 = no dropout)')
parser.add_argument('--dropoute', type=float, default=0.1,
                    help='dropout to remove words from embedding layer (0 = no dropout)')
parser.add_argument('--dropoutl', type=float, default=-0.2,
                    help='dropout applied to layers (0 = no dropout)')
parser.add_argument('--wdrop', type=float, default=0.5,
                    help='amount of weight dropout to apply to the RNN hidden to hidden matrix')
parser.add_argument('--tied', action='store_false',
                    help='tie the word embedding and softmax weights')
parser.add_argument('--seed', type=int, default=1111,
                    help='random seed')
parser.add_argument('--nonmono', type=int, default=5,
                    help='random seed')
parser.add_argument('--cuda', action='store_false',
                    help='use CUDA')
parser.add_argument('--log-interval', type=int, default=200, metavar='N',
                    help='report interval')
parser.add_argument('--save', type=str,  default='EXP',
                    help='path to save the final model')
parser.add_argument('--alpha', type=float, default=2,
                    help='alpha L2 regularization on RNN activation (alpha = 0 means no regularization)')
parser.add_argument('--beta', type=float, default=1,
                    help='beta slowness regularization applied on RNN activiation (beta = 0 means no regularization)')
parser.add_argument('--wdecay', type=float, default=1.2e-6,
                    help='weight decay applied to all weights')
parser.add_argument('--continue_train', action='store_true',
                    help='continue train from a checkpoint')
parser.add_argument('--n_experts', type=int, default=10,
                    help='number of experts')
parser.add_argument('--small_batch_size', type=int, default=-1,
                    help='the batch size for computation. batch_size should be divisible by small_batch_size.\
                     In our implementation, we compute gradients with small_batch_size multiple times, and accumulate the gradients\
                     until batch_size is reached. An update step is then performed.')
parser.add_argument('--max_seq_len_delta', type=int, default=40,
                    help='max sequence length')
parser.add_argument('--single_gpu', default=False, action='store_true', 
                    help='use single GPU')
                    
# LM robustness
parser.add_argument('--ndistilstudents', type=int, default=0,
                    help='number state  distillation students per layer')
parser.add_argument('--distillossw', type=float, default=1.0,
                    help='student distillation loss weight')
parser.add_argument('--no_average_ensemble', action='store_true',
                    help='disable average ensemble, use only master')

# Additional stats
parser.add_argument('--per_token_state_norm_out_file', type=str, default='',
                    help='output per-token top rnn state norm to the specified file')                    
parser.add_argument('--per_token_entropy_out_file', type=str, default='',
                    help='output per-token entropy to the specified file')                    


args = parser.parse_args()

if args.nhidlast < 0:
    args.nhidlast = args.emsize
if args.dropoutl < 0:
    args.dropoutl = args.dropouth
if args.small_batch_size < 0:
    args.small_batch_size = args.batch_size

def logging(s, print_=True, log_=True):
    if print_:
        print(s)
    if log_:
        with open(os.path.join(args.save, 'log.txt'), 'a+') as f_log:
            f_log.write(s + '\n')

# Set the random seed manually for reproducibility.
np.random.seed(args.seed)
torch.manual_seed(args.seed)
if torch.cuda.is_available():
    if not args.cuda:
        print("WARNING: You have a CUDA device, so you should probably run with --cuda")
    else:
        torch.cuda.manual_seed_all(args.seed)

###############################################################################
# Load data
###############################################################################

vocab_path = os.path.join(args.save, 'vocab.pickle')
with open(vocab_path, 'rb') as vocab_file:
    vocab = pickle.load(vocab_file) 

corpus = data.SentTestCorpus(args.test_data, vocab)

test_batch_size = 1
#test_batch_size = args.batch_size


###############################################################################
# Evaluating code
###############################################################################

def evaluate_by_sentence(test_sentences, test_batch_size, args, average_ensemble,
                         per_token_state_norm_out_fs=None, per_token_entropy_out_fs=None):
    for sent_id, sent in enumerate(test_sentences):
        if len(sent) < 2:
            print("smallsent")
            continue
        test_data, test_mask = eval_batchify(sent, test_batch_size, args)
        test_loss = evaluate(test_data, test_mask, test_batch_size, average_ensemble=average_ensemble,
                             per_token_state_norm_out_fs=per_token_state_norm_out_fs, 
                             per_token_entropy_out_fs=per_token_entropy_out_fs)
        print(len(sent), test_loss, math.exp(test_loss))
        if per_token_state_norm_out_fs is not None:
            print("\n", file=per_token_state_norm_out_fs)
        if per_token_entropy_out_fs is not None:
            print("\n", file=per_token_entropy_out_fs)


def evaluate(data_source, data_source_mask, batch_size=10, average_ensemble=True,
             per_token_state_norm_out_fs=None, per_token_entropy_out_fs=None):
    # Turn on evaluation mode which disables dropout.
    model.eval()
    total_loss = 0
    ntokens = len(corpus.vocab)
    hidden = model.init_hidden(batch_size)
    with torch.no_grad():
        data, targets, mask = get_eval_batch(data_source, data_source_mask, 0, args)
        masked_targets = targets * mask -100 * (1-mask)     # -100 is the masking value for targets
        masked_targets = masked_targets.view(-1)

        mrv = parallel_model(*hidden, input=data, average_ensemble=average_ensemble, return_h=per_token_state_norm_out_fs)
        if not per_token_state_norm_out_fs:
            log_prob, hidden = mrv
        else:
            log_prob, hidden, _, output_vector = mrv
            output_vector = output_vector[-1]
        loss = nn.functional.nll_loss(log_prob.view(-1, log_prob.size(2)), masked_targets, ignore_index=-100).data

        total_loss += loss * len(data)

        hidden = repackage_hidden(hidden)
        avg_total_loss = total_loss.item() / len(data_source)
        
        if per_token_state_norm_out_fs:
            for i in range(output_vector.shape[0]):
                norm_val = output_vector[i].norm().item()
                print(norm_val, end=' ', file=per_token_state_norm_out_fs)
                
        if per_token_entropy_out_fs:
            for i in range(output_vector.shape[0]):
                logits = log_prob[i,0]
                entropy_val = torch.distributions.categorical.Categorical(logits=logits).entropy().item()
                print(entropy_val, end=' ', file=per_token_entropy_out_fs)
                
    return avg_total_loss


# Load the best saved model.
model = torch.load(os.path.join(args.save, 'model.pt'))
model.rnd_pre_apply = False
model.state_post_proc_pre_update=False
model.state_proc_only_on_last_layer=False
#parallel_model = nn.DataParallel(model.cuda(), dim=1)
parallel_model = model.cuda()

per_token_state_norm_out_fs = open(args.per_token_state_norm_out_file, "w") if args.per_token_state_norm_out_file else None
per_token_entropy_out_fs = open(args.per_token_entropy_out_file, "w") if args.per_token_entropy_out_file else None

# Run on test data.
evaluate_by_sentence(corpus.test_sentences, test_batch_size, args, average_ensemble=not args.no_average_ensemble,
                     per_token_state_norm_out_fs=per_token_state_norm_out_fs, 
                     per_token_entropy_out_fs=per_token_entropy_out_fs)

#logging('=' * 89)
#logging('| Test set: %s' % args.test_data)
#logging('| Evaluation results | test loss {:5.2f} | test ppl {:8.2f}'.format(
#    test_loss, math.exp(test_loss)))
#logging('=' * 89)

if per_token_state_norm_out_fs is not None:
    per_token_state_norm_out_fs.close()
if per_token_entropy_out_fs is not None:
    per_token_entropy_out_fs.close()
    
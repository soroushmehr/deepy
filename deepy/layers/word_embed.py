#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import theano.tensor as T
from deepy.layers import NeuralLayer
from deepy.utils import FLOATX

class WordEmbedding(NeuralLayer):
    """
    Word embedding layer.
    The word embeddings are randomly initialized, and are learned over the time.
    """
    def __init__(self, size, vocab_size, zero_index=None, mask=None):
        super(WordEmbedding, self).__init__("word_embed")
        self.size = size
        self.vocab_size = vocab_size
        self.output_dim = size
        self.zero_index = zero_index
        self.mask = mask

    def prepare(self):
        self.embed_matrix = self.create_weight(self.vocab_size, self.size, "embed")
        self.register_parameters(self.embed_matrix)

    def output(self, x):
        if self.zero_index is not None or self.mask:
            mask = T.neq(x, self.zero_index) if not self.mask else self.mask
            # To avoid negative index
            x *= mask
        else:
            mask = None

        ret_tensor = self.embed_matrix[x.flatten()].reshape(list(x.shape) + [self.size])

        if mask:
            if x.ndim == 2:
                ret_tensor *= mask[:, :, None]
            elif x.ndim == 1:
                ret_tensor *= mask[:, None]
        return ret_tensor

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from . import NeuralLayer
from deepy.utils import build_activation, FLOATX
import numpy as np
import theano
import theano.tensor as T

OUTPUT_TYPES = ["sequence", "one"]
INPUT_TYPES = ["sequence", "one"]

class RNN(NeuralLayer):
    """
    Recurrent neural network layer.
    """

    def __init__(self, hidden_size, input_type="sequence", output_type="sequence", vector_core=None,
                 hidden_activation="tanh", hidden_init=None, input_init=None, steps=None,
                 persistent_state=False, reset_state_for_input=None, batch_size=None,
                 go_backwards=False, mask=None, second_input_size=None, second_input=None):
        super(RNN, self).__init__("rnn")
        self._hidden_size = hidden_size
        self.output_dim = self._hidden_size
        self._input_type = input_type
        self._output_type = output_type
        self._hidden_activation = hidden_activation
        self._hidden_init = hidden_init
        self._vector_core = vector_core
        self._input_init = input_init
        self.persistent_state = persistent_state
        self.reset_state_for_input = reset_state_for_input
        self.batch_size = batch_size
        self._steps = steps
        self._go_backwards = go_backwards
        self._mask = mask.dimshuffle((1,0)) if mask else None
        self._second_input_size = second_input_size
        self._second_input = second_input
        if input_type not in INPUT_TYPES:
            raise Exception("Input type of RNN is wrong: %s" % input_type)
        if output_type not in OUTPUT_TYPES:
            raise Exception("Output type of RNN is wrong: %s" % output_type)
        if self.persistent_state and not self.batch_size:
            raise Exception("Batch size must be set for persistent state mode")
        if mask and input_type == "one":
            raise Exception("Mask only works with sequence input")

    def _hidden_preact(self, h):
        return T.dot(h, self.W_h) if not self._vector_core else h * self.W_h


    def step(self, *variables):
        mask = None
        if self._input_type == "sequence":
            x, h = variables[-2:]
            if self._second_input_size:
                second_input = variables[0]
                second_z = T.dot(second_input, self.W_i2)
                variables = variables[1:]
            else:
                second_z = 0
            if self._mask:
                mask = variables[0]
            # Reset part of the state on condition
            if self.reset_state_for_input != None:
                h = h * T.neq(x[:, self.reset_state_for_input], 1).dimshuffle(0, 'x')
            z = T.dot(x, self.W_i) + self._hidden_preact(h) + self.B_h + second_z
        else:
            h, = variables
            z = self._hidden_preact(h) + self.B_h

        new_h = self._hidden_act(z)
        # Apply mask
        if mask:
            mask = mask.dimshuffle(0, 'x')
            new_h = mask * new_h + (1 - mask) * h
        return new_h

    def produce_input_sequences(self, x, mask=None, second_input=None):
        sequences = [x]
        # Second input
        if second_input:
            sequences.insert(0, second_input)
        elif self._second_input:
            sequences.insert(0, self._second_input)
        # Mask
        if mask:
            # (batch)
            sequences.insert(0, mask)
        elif self._mask:
            # (time, batch)
            sequences.insert(0, self._mask)
        return sequences

    def produce_initial_states(self, x):
        h0 = T.alloc(np.cast[FLOATX](0.), x.shape[0], self._hidden_size)
        if self._input_type == "sequence":
            if self.persistent_state:
                h0 = self.state
        else:
            h0 = x
        return [h0]

    def output(self, x):
        if self._input_type == "sequence":
            # Move middle dimension to left-most position
            # (sequence, batch, value)
            sequences = self.produce_input_sequences(x.dimshuffle((1,0,2)))
        else:
            sequences = []
        step_outputs = self.produce_initial_states(x)
        hiddens, _ = theano.scan(self.step, sequences=sequences, outputs_info=step_outputs,
                                 n_steps=self._steps, go_backwards=self._go_backwards)

        # Save persistent state
        if self.persistent_state:
            self.register_updates((self.state, hiddens[-1]))

        if self._output_type == "one":
            return hiddens[-1]
        elif self._output_type == "sequence":
            return hiddens.dimshuffle((1,0,2))

    def setup(self):
        if self._input_type == "one" and self.input_dim != self._hidden_size:
            raise Exception("For RNN receives one vector as input, "
                            "the hidden size should be same as last output dimension.")
        self._setup_params()
        self._setup_functions()

    def _setup_functions(self):
        self._hidden_act = build_activation(self._hidden_activation)

    def _setup_params(self):
        if not self._vector_core:
            self.W_h = self.create_weight(self._hidden_size, self._hidden_size, suffix="h", initializer=self._hidden_init)
        else:
            self.W_h = self.create_bias(self._hidden_size, suffix="h")
            self.W_h.set_value(self.W_h.get_value() + self._vector_core)
        self.B_h = self.create_bias(self._hidden_size, suffix="h")

        self.register_parameters(self.W_h, self.B_h)

        if self.persistent_state:
            self.state = self.create_matrix(self.batch_size, self._hidden_size, "rnn_state")
            self.register_free_parameters(self.state)
        else:
            self.state = None

        if self._input_type == "sequence":
            self.W_i = self.create_weight(self.input_dim, self._hidden_size, suffix="i", initializer=self._input_init)
            self.register_parameters(self.W_i)
        if self._second_input_size:
            self.W_i2 = self.create_weight(self._second_input_size, self._hidden_size, suffix="i2", initializer=self._input_init)
            self.register_parameters(self.W_i2)

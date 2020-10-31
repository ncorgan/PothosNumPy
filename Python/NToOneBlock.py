# Copyright (c) 2019-2020 Nicholas Corgan
# SPDX-License-Identifier: BSD-3-Clause

from .BaseBlock import *

import Pothos

import functools
import numpy

class NToOneBlock(BaseBlock):
    def __init__(self, blockPath, func, inputDType, outputDType, inputDTypeArgs, outputDTypeArgs, nchans, *funcArgs, **kwargs):
        if inputDType is None:
            raise ValueError("For non-source blocks, inputDType cannot be None.")
        if outputDType is None:
            raise ValueError("For non-sink blocks, outputDType cannot be None.")

        BaseBlock.__init__(self, blockPath, func, inputDType, outputDType, inputDTypeArgs, outputDTypeArgs, *funcArgs, **kwargs)

        self.callReduce = kwargs.get("callReduce", True)

        self.nchans = 0 # Set this here because attempting to query it before it exists
                        # will attempt to call a Pothos getter.
        self.setNumChannels(nchans)
        self.setupOutput(0, self.outputDType)

    def numChannels(self):
        return self.nchans

    def setNumChannels(self, nchans):
        if nchans <= 0:
            raise ValueError("Number of channels must be positive.")

        oldNChans = self.nchans
        for i in range(oldNChans, nchans):
            self.setupInput(i, self.inputDType)

        self.nchans = nchans

    def work(self):
        assert(self.numpyInputDType is not None)
        assert(self.numpyOutputDType is not None)

        if self.callPostBuffer:
            self.workWithPostBuffer()
        else:
            self.workWithGivenOutputBuffer()

    def workWithPostBuffer(self):
        elems = self.workInfo().minAllInElements
        if 0 == elems:
            return

        N = min(elems, len(self.output(0).buffer()))

        # This creates a 2D ndarray containing the array subsets we're interested
        # in. This points to the input buffers themselves without copying memory.
        allArrs = numpy.array([buf.buffer()[:N].view() for buf in self.inputs()], dtype=self.numpyInputDType)
        out = None

        if self.callReduce:
            out = functools.reduce(self.func, allArrs, *self.funcArgs)
        else:
            out = self.func(allArrs, *self.funcArgs, **self.funcKWargs)

        if (out is not None) and (len(out) > 0):
            for port in self.inputs():
                port.consume(N)
            self.output(0).postBuffer(out)

    def workWithGivenOutputBuffer(self):
        elems = self.workInfo().minAllElements
        if 0 == elems:
            return

        # This creates a 2D ndarray containing the array subsets we're interested
        # in. This points to the input buffers themselves without copying memory.
        allArrs = numpy.array([buf.buffer()[:elems].view() for buf in self.inputs()], dtype=self.numpyInputDType)
        out0 = self.output(0).buffer()
        out = None

        if self.callReduce:
            out = functools.reduce(self.func, allArrs, *self.funcArgs)
        else:
            out = self.func(allArrs, *self.funcArgs, **self.funcKWargs)

        if (out is not None) and (len(out) > 0):
            for port in self.inputs():
                port.consume(elems)

            out0[:elems] = out
            self.output(0).produce(elems)

import pytest
import numpy as np
import theano.tensor as T
import yann.core.activations as A

@pytest.fixture(scope='module')
def generator (activation):
    def test(self):
        theano_input = T.matrix()
        numpy_input = np.random.uniform(-4, 4, (5, 5))  # Create some 5X5 matrix randomly     
        theano_test_function = getattr(A,activation)
        np_test_function = getattr(self, activation) # for every activation write a np version 
        theano_result = theano_test_function(theano_input).eval({theano_input: numpy_input})    
        np_result = np_test_function(numpy_input)            
        assert np.allclose(theano_result, np_result)       
    return test

class TestActivations:
    def setup_method(self):
        test_activations = ['Abs','ReLU','Sigmoid','Tanh','Softmax','Squared']            
        for activation in test_activations:
            test_name = 'test_' + activation
            test = generator(activation)
            setattr(self,test_name, test)    
    def Abs(self, x): return np.abs(x)
    def ReLU(self, x): return x * (x > 0)
    def Sigmoid(self, x): return 1 / (1 + np.exp(-x))
    def Tanh(self, x): return np.tanh(x)
    def Softmax(self, x): return (np.exp(x).T / np.exp(x).sum(-1)).T
    def Squared(self, x): return x**2        


#!/usr/bin/python

# General Packages
import os
from collections import OrderedDict
import cPickle, gzip

# Math Packages
import numpy
import cv2
import time
from math import floor

# Theano Packages
import theano
import theano.tensor as T
from theano.ifelse import ifelse

# CNN code packages
import cnn
import util
import loaders

class network(object):

    def __init__(  self, random_seed,
                         filename_params, 
                         verbose = False, 
                        ):

        self.results_file_name   = filename_params [ "results_file_name" ]                
        # Files that will be saved down on completion Can be used by the parse.m file
        self.error_file_name     = filename_params [ "error_file_name" ]
        self.cost_file_name      = filename_params [ "cost_file_name"  ]
        self.confusion_file_name = filename_params [ "confusion_file_name" ]
        self.network_save_name   = filename_params [ "network_save_name" ]
        
        self.rng = numpy.random.RandomState(random_seed)  
        self. main_img_visual = True 
       
    def save_network( self ):          # for others use only data_params or optimization_params

        f = gzip.open(self.network_save_name, 'wb')
        for obj in [self.params, self.arch, self.data_struct, self.optim_params]:
            cPickle.dump(obj, f, protocol = cPickle.HIGHEST_PROTOCOL)
        f.close()   
                
    # Load initial data          
    def init_data(self, data_params, outs):
        
        self.data_struct         = data_params # This command makes it possible to save down
        self.dataset             = data_params [ "loc" ]
        self.data_type           = data_params [ "type" ]
        self.height              = data_params [ "height" ]
        self.width               = data_params [ "width" ]
        self.batch_size          = data_params [ "batch_size" ]    
        self.load_batches        = data_params [ "load_batches"  ] * self.batch_size
        if self.load_batches < self.batch_size and (self.dataset == "caltech101" or self.dataset == "caltech256"):
            AssertionError("load_batches is improper for this self.dataset " + self.dataset)
        self.batches2train       = data_params [ "batches2train" ]
        self.batches2test        = data_params [ "batches2test" ]
        self.batches2validate    = data_params [ "batches2validate" ] 
        self.channels            = data_params [ "channels" ]
        
        
        print "... loading data"
        start_time = time.clock()
        # load matlab files as self.dataset.
        if self.data_type == 'mat':
            train_data_x, train_data_y, train_data_y1 = loaders.load_data_mat(dataset = self.dataset, batch = 1 , type_set = 'train' , n_classes = outs)             
            test_data_x, test_data_y, valid_data_y1 = loaders.load_data_mat(dataset = self.dataset, batch = 1 , type_set = 'test' , n_classes = outs)      
            valid_data_x, valid_data_y, test_data_y1 = loaders.load_data_mat(dataset = self.dataset, batch = 1 , type_set = 'valid' , n_classes = outs)   

            self.train_set_x = theano.shared(numpy.asarray(train_data_x, dtype=theano.config.floatX), borrow=True)
            self.train_set_y = theano.shared(numpy.asarray(train_data_y, dtype='int32'), borrow=True)
            self.train_set_y1 = theano.shared(numpy.asarray(train_data_y1, dtype=theano.config.floatX), borrow=True)
    
            self.test_set_x = theano.shared(numpy.asarray(test_data_x, dtype=theano.config.floatX), borrow=True)
            self.test_set_y = theano.shared(numpy.asarray(test_data_y, dtype='int32'), borrow=True) 
            self.test_set_y1 = theano.shared(numpy.asarray(test_data_y1, dtype=theano.config.floatX), borrow=True)
    
            self.valid_set_x = theano.shared(numpy.asarray(valid_data_x, dtype=theano.config.floatX), borrow=True)
            self.valid_set_y = theano.shared(numpy.asarray(valid_data_y, dtype='int32'), borrow=True)
            self.valid_set_y1 = theano.shared(numpy.asarray(valid_data_y1, dtype=theano.config.floatX), borrow=True)
    
            # compute number of minibatches for training, validation and testing
            self.n_train_batches = self.train_set_x.get_value(borrow=True).shape[0] / self.batch_size
            self.n_valid_batches = self.valid_set_x.get_value(borrow=True).shape[0] / self.batch_size
            self.n_test_batches = self.test_set_x.get_value(borrow=True).shape[0] / self.batch_size
    
            self.multi_load = True
    
        # load pkl data as is shown in theano tutorials
        elif self.data_type == 'pkl':   
    
            data = loaders.load_data_pkl(self.dataset)
            self.train_set_x, self.train_set_y, self.train_set_y1 = data[0]
            self.valid_set_x, self.valid_set_y, self.valid_set_y1 = data[1]
            self.test_set_x, self.test_set_y, self.test_set_y1 = data[2]
    
             # compute number of minibatches for training, validation and testing
            self.n_train_batches = self.train_set_x.get_value(borrow=True).shape[0] / self.batch_size
            self.n_valid_batches = self.valid_set_x.get_value(borrow=True).shape[0] / self.batch_size
            self.n_test_batches = self.test_set_x.get_value(borrow=True).shape[0] / self.batch_size
    
            n_train_images = self.train_set_x.get_value(borrow=True).shape[0]
            n_test_images = self.test_set_x.get_value(borrow=True).shape[0]
            n_valid_images = self.valid_set_x.get_value(borrow=True).shape[0]
    
            n_train_batches_all = n_train_images / self.batch_size 
            n_test_batches_all = n_test_images / self.batch_size 
            n_valid_batches_all = n_valid_images / self.batch_size
    
            if ( (n_train_batches_all < self.batches2train) or 
                    (n_test_batches_all < self.batches2test) or 
                      (n_valid_batches_all < self.batches2validate) ):   
                # You can't have so many batches.
                print "...  !! self.dataset doens't have so many batches. "
                raise AssertionError()
    
            self.multi_load = False
    
        # load skdata ( its a good library that has a lot of self.datasets)
        elif self.data_type == 'skdata':
    
            if (self.dataset == 'mnist' or 
                self.dataset == 'mnist_noise1' or 
                self.dataset == 'mnist_noise2' or
                self.dataset == 'mnist_noise3' or
                self.dataset == 'mnist_noise4' or
                self.dataset == 'mnist_noise5' or
                self.dataset == 'mnist_noise6' or
                self.dataset == 'mnist_bg_images' or
                self.dataset == 'mnist_bg_rand' or
                self.dataset == 'mnist_rotated' or
                self.dataset == 'mnist_rotated_bg') :
    
                print "... importing " + self.dataset + " from skdata"
                data = getattr(loaders, 'load_skdata_' + self.dataset)()                

                self.train_set_x, self.train_set_y, self.train_set_y1 = data[0]
                self.valid_set_x, self.valid_set_y, self.valid_set_y1 = data[1]
                self.test_set_x, self.test_set_y, self.test_set_y1 = data[2]
    
                # compute number of minibatches for training, validation and testing
                self.n_train_batches = self.train_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_valid_batches = self.valid_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_test_batches = self.test_set_x.get_value(borrow=True).shape[0] / self.batch_size
    
                n_train_images = self.train_set_x.get_value(borrow=True).shape[0]
                n_test_images = self.test_set_x.get_value(borrow=True).shape[0]
                n_valid_images = self.valid_set_x.get_value(borrow=True).shape[0]
    
                n_train_batches_all = n_train_images / self.batch_size 
                n_test_batches_all = n_test_images / self.batch_size 
                n_valid_batches_all = n_valid_images / self.batch_size
    
                if ( (n_train_batches_all < self.batches2train) or 
                       (n_test_batches_all < self.batches2test) or 
                         (n_valid_batches_all < self.batches2validate) ): 
                    # You can't have so many batches.
                    print "...  !! self.dataset doens't have so many batches. "
                    raise AssertionError()
    
                self.multi_load = False
    
            elif self.dataset == 'cifar10':
                print "... importing cifar 10 from skdata"
    
                data = loaders.load_skdata_cifar10()
                self.train_set_x, self.train_set_y, self.train_set_y1 = data[0]
                self.valid_set_x, self.valid_set_y, self.valid_set_y1 = data[1]
                self.test_set_x, self.test_set_y, self.test_set_y1 = data[2]
    
                # compute number of minibatches for training, validation and testing
                self.n_train_batches = self.train_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_valid_batches = self.valid_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_test_batches = self.test_set_x.get_value(borrow=True).shape[0] / self.batch_size
    
                self.multi_load = False
    
            elif self.dataset == 'caltech101':
                print "... importing caltech 101 from skdata"
    
                # shuffle the data
                total_images_in_dataset = 9144 
                self.rand_perm = numpy.random.permutation(total_images_in_dataset)  
                # create a constant shuffle, so that data can be loaded in batchmode with the same random shuffle
    
                n_train_images = total_images_in_dataset / 3
                n_test_images = total_images_in_dataset / 3
                n_valid_images = total_images_in_dataset / 3 
    
                n_train_batches_all = n_train_images / self.batch_size 
                n_test_batches_all = n_test_images / self.batch_size 
                n_valid_batches_all = n_valid_images / self.batch_size
    
                if ( (n_train_batches_all < self.batches2train) or 
                        (n_test_batches_all < self.batches2test) or 
                        (n_valid_batches_all < self.batches2validate) ): 
                    # You can't have so many batches.
                    print "...  !! self.dataset doens't have so many batches. "
                    raise AssertionError()
    
                train_data_x, train_data_y  = loaders.load_skdata_caltech101(
                                                 batch_size = self.load_batches, 
                                                  rand_perm = self.rand_perm, 
                                                  batch = 1 , 
                                                  type_set = 'train' ,
                                                  height = self.height,
                                                  width = self.width)             
                test_data_x, test_data_y  = loaders.load_skdata_caltech101(
                                                 batch_size = self.load_batches,
                                                 rand_perm = self.rand_perm,
                                                 batch = 1 ,
                                                 type_set = 'test' , 
                                                 height = self.height,
                                                 width = self.width)      
                valid_data_x, valid_data_y  = loaders.load_skdata_caltech101(
                                                 batch_size = self.load_batches, 
                                                 rand_perm = self.rand_perm,
                                                 batch = 1 , 
                                                 type_set = 'valid' , 
                                                 height = self.height, 
                                                 width = self.width)

    
                self.train_set_x = theano.shared(train_data_x, borrow=True)
                self.train_set_y = theano.shared(train_data_y, borrow=True)
                
                self.test_set_x = theano.shared(test_data_x, borrow=True)
                self.test_set_y = theano.shared(test_data_y, borrow=True) 
              
                self.valid_set_x = theano.shared(valid_data_x, borrow=True)
                self.valid_set_y = theano.shared(valid_data_y, borrow=True)
    
                # compute number of minibatches for training, validation and testing
                self.n_train_batches = self.train_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_valid_batches = self.valid_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_test_batches = self.test_set_x.get_value(borrow=True).shape[0] / self.batch_size
    
                self.multi_load = True
    
            elif self.dataset == 'caltech256':
                print "... importing caltech 256 from skdata"
    
                    # shuffle the data
                total_images_in_dataset = 30607 
                self.rand_perm = numpy.random.permutation(total_images_in_dataset)  # create a constant shuffle, so that data can be loaded in batchmode with the same random shuffle
    
                n_train_images = total_images_in_dataset / 3
                n_test_images = total_images_in_dataset / 3
                n_valid_images = total_images_in_dataset / 3 
    
                n_train_batches_all = n_train_images / self.batch_size 
                n_test_batches_all = n_test_images / self.batch_size 
                n_valid_batches_all = n_valid_images / self.batch_size
    
                if ( (n_train_batches_all < self.batches2train) or 
                     (n_test_batches_all < self.batches2test) or  
                     (n_valid_batches_all < self.batches2validate) ):        # You can't have so many batches.
                    print "...  !! self.dataset doens't have so many batches. "
                    raise AssertionError()
    
                
                train_data_x, train_data_y = loaders.load_skdata_caltech256(
                                                 batch_size = self.load_batches, 
                                                  rand_perm = self.rand_perm, 
                                                  batch = 1 , 
                                                  type_set = 'train' ,
                                                  height = self.height,
                                                  width = self.width)             
                test_data_x, test_data_y  = loaders.load_skdata_caltech256(
                                                 batch_size = self.load_batches,
                                                 rand_perm = self.rand_perm,
                                                 batch = 1 ,
                                                 type_set = 'test' , 
                                                 height = self.height,
                                                 width = self.width)      
                valid_data_x, valid_data_y  = loaders.load_skdata_caltech256(
                                                 batch_size = self.load_batches, 
                                                 rand_perm = self.rand_perm,
                                                 batch = 1 , 
                                                 type_set = 'valid' , 
                                                 height = self.height, 
                                                 width = self.width)

                self.train_set_x = theano.shared(train_data_x, borrow=True)
                self.train_set_y = theano.shared(train_data_y, borrow=True)
                
                self.test_set_x = theano.shared(test_data_x, borrow=True)
                self.test_set_y = theano.shared(test_data_y, borrow=True) 
              
                self.valid_set_x = theano.shared(valid_data_x, borrow=True)
                self.valid_set_y = theano.shared(valid_data_y, borrow=True)
    
                # compute number of minibatches for training, validation and testing
                self.n_train_batches = self.train_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_valid_batches = self.valid_set_x.get_value(borrow=True).shape[0] / self.batch_size
                self.n_test_batches = self.test_set_x.get_value(borrow=True).shape[0] / self.batch_size
    
                self.multi_load = True
    
        assert ( self.height * self.width * self.channels == 
                self.train_set_x.get_value( borrow = True ).shape[1] )
        end_time = time.clock()
        print "...         time taken is " +str(end_time - start_time) + " seconds"
        
    # Class initialization complete.
        
    # define the optimzer function 
    def build_network (self, arch_params, optimization_params , init_params = None, verbose = True):    
    
        self.optim_params                    = optimization_params
        self.mom_start                       = optimization_params [ "mom_start" ]
        self.mom_end                         = optimization_params [ "mom_end" ]
        self.mom_epoch_interval              = optimization_params [ "mom_interval" ]
        self.mom_type                        = optimization_params [ "mom_type" ]
        self.initial_learning_rate           = optimization_params [ "initial_learning_rate" ]              
        self.learning_rate_decay             = optimization_params [ "learning_rate_decay" ] 
        self.ada_grad                        = optimization_params [ "ada_grad" ]   
        self.fudge_factor                    = optimization_params [ "fudge_factor" ]
        self.l1_reg                          = optimization_params [ "l1_reg" ]
        self.l2_reg                          = optimization_params [ "l2_reg" ]
        self.rms_prop                        = optimization_params [ "rms_prop" ]
        self.rms_rho                         = optimization_params [ "rms_rho" ]
        self.rms_epsilon                     = optimization_params [ "rms_epsilon" ]
        self.objective                       = optimization_params [ "objective" ]        
    
        self.arch                            = arch_params
        self.squared_filter_length_limit     = arch_params [ "squared_filter_length_limit" ]   
        self.mlp_activations                 = arch_params [ "mlp_activations"  ] 
        self.cnn_activations                 = arch_params [ "cnn_activations" ]
        self.cnn_dropout                     = arch_params [ "cnn_dropout"  ]
        self.mlp_dropout                     = arch_params [ "mlp_dropout"  ]
        self.batch_norm                      = arch_params [ "batch_norm"  ]    
        self.mlp_dropout_rates               = arch_params [ "mlp_dropout_rates" ]
        self.cnn_dropout_rates               = arch_params [ "cnn_dropout_rates" ]
        self.nkerns                          = arch_params [ "nkerns"  ]
        self.outs                            = arch_params [ "outs" ]
        self.filter_size                     = arch_params [ "filter_size" ]
        self.pooling_size                    = arch_params [ "pooling_size" ]
        self.num_nodes                       = arch_params [ "num_nodes" ]
        random_seed                          = arch_params [ "random_seed" ]
        self.svm_flag                        = arch_params [ "svm_flag" ]   
        self.max_out                         = arch_params [ "max_out" ] 
        self.cnn_maxout                      = arch_params [ "cnn_maxout" ]   
        self.mlp_maxout                      = arch_params [ "mlp_maxout" ]
                    
        if self.ada_grad is True:
            assert self.rms_prop is False
        elif self.rms_prop is True:
            assert self.ada_grad is False
            self.fudge_factor = self.rms_epsilon
       
        print '... building the network'    
        
        
        start_time = time.clock()
        # allocate symbolic variables for the data
        index = T.lscalar('index')  # index to a [mini]batch
        x = T.matrix('x')           # the data is presented as rasterized images
        y = T.ivector('y')          # the labels are presented as 1D vector of [int] 
            
        if self.svm_flag is True:
            y1 = T.matrix('y1')     # [-1 , 1] labels in case of SVM    
     
        first_layer_input = x.reshape((self.batch_size, self.channels, self.height, self.width))
    
        # Create first convolutional - pooling layers 
        activity = []       # to record Cnn activities 
        self.weights = []
    
        conv_layers = []         
        dropout_conv_layers = [] 
        
        if not self.nkerns == []:
            filt_size = self.filter_size[0]
            pool_size = self.pooling_size[0]
        if self.max_out > 0:     
            max_out_size = self.cnn_maxout[0]
        else: 
            max_out_size = 1

        next_in = [ self.height, self.width, self.channels]
        stack_size = 1 
        param_counter = 0 
        
        if not self.nkerns == []:     
            if len(filt_size) == 2:        
                dropout_conv_layers.append ( 
                                cnn.DropoutConv2DPoolLayer(
                                        rng = self.rng,
                                        input = first_layer_input,
                                        image_shape=(self.batch_size, self.channels , self.height, self.width),
                                        filter_shape=(self.nkerns[0], self.channels , filt_size[0], filt_size[1]),
                                        poolsize = pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[0],
                                        W = None if init_params is None else init_params[param_counter],
                                        b = None if init_params is None else init_params[param_counter + 1], 
                                        batch_norm = self.batch_norm,
                                        alpha = None if init_params is None else init_params[param_counter + 2],
                                        p = self.cnn_dropout_rates[0]                                      
                                         ) ) 
                conv_layers.append ( 
                                cnn.Conv2DPoolLayer(
                                        rng = self.rng,
                                        input = first_layer_input,
                                        image_shape=(self.batch_size, self.channels , self.height, self.width),
                                        filter_shape=(self.nkerns[0], self.channels , filt_size[0], filt_size[1]),
                                        poolsize = pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[0],
                                        W = dropout_conv_layers[-1].params[0] ,
                                        b = dropout_conv_layers[-1].params[1],
                                        batch_norm = self.batch_norm,
                                        alpha = dropout_conv_layers[-1].alpha,
                                        verbose = verbose
                                         ) )  
                next_in[0] = int(floor(( self.height - filt_size [0] + 1 ))) / (pool_size[0] )       
                next_in[1] = int(floor(( self.width - filt_size[1] + 1 ))) / (pool_size[1] )    
                next_in[2] = self.nkerns[0]  / max_out_size                                                                                                                 
            elif len(filt_size) == 3:
                dropout_conv_layers.append ( 
                                cnn.DropoutConv3DPoolLayer(
                                        rng = self.rng,
                                        input = first_layer_input,
                                        image_shape=(self.batch_size, self.channels , stack_size, self.height, self.width),
                                        filter_shape=(self.nkerns[0], filt_size[0] , stack_size, filt_size[1], filt_size[2]),
                                        poolsize=pool_size,                                        
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[0],
                                        W = None if init_params is None else init_params[param_counter],
                                        b = None if init_params is None else init_params[param_counter + 1],
                                        batch_norm = self.batch_norm,
                                        alpha = None if init_params is None else init_params[param_counter + 2],
                                        p = self.cnn_dropout_rates[0]                             
                                         ) )
                conv_layers.append ( 
                                cnn.Conv3DPoolLayer(
                                        rng = self.rng,
                                        input = first_layer_input,
                                        image_shape=(self.batch_size, self.channels , stack_size, self.height, self.width),
                                        filter_shape=(self.nkerns[0], filt_size[0] , stack_size, filt_size[1], filt_size[2]),
                                        poolsize=pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,                                        
                                        activation = self.cnn_activations[0],
                                        W = dropout_conv_layers[-1].params[0] ,
                                        b = dropout_conv_layers[-1].params[1],
                                        batch_norm = self.batch_norm,
                                        alpha = dropout_conv_layers[-1].alpha, 
                                        verbose = verbose
                                         ) )
                                                                                  
                next_in[0] = int(floor( ( self.height - filt_size [1] + 1 ))) / (pool_size[1] * max_out_size[1])      
                next_in[1] = int(floor(( self.width - filt_size[2] + 1 ))) / (pool_size[2] * max_out_size[1])
                next_in[2] = int(floor(self.nkerns[0] * (self.channels - filt_size[0] + 1))) / (pool_size[0] * max_out_size[0])

                   
            else:
                print "!! So far Samosa is only capable of 2D and 3D conv layers."                               
                sys.exit()
            activity.append ( conv_layers[-1].output )
            self.weights.append ( conv_layers[-1].filter_img)
    
    
            # Create the rest of the convolutional - pooling layers in a loop
            param_counter = param_counter + 2      
            if self.batch_norm is True:
                param_counter = param_counter + 1
            for layer in xrange(len(self.nkerns)-1):   
                
                filt_size = self.filter_size[layer+1]
                pool_size = self.pooling_size[layer+1]
                if self.max_out > 0:
                    max_out_size = self.cnn_maxout[layer+1]
                else:
                    max_out_size = 1 

                if len(filt_size) == 2:
                    
                    dropout_conv_layers.append ( 
                                    cnn.DropoutConv2DPoolLayer(
                                        rng = self.rng,
                                        input = conv_layers[layer].output,        
                                        image_shape=(self.batch_size, next_in[2], next_in[0], next_in[1]),
                                        filter_shape=(self.nkerns[layer+1], next_in[2], filt_size[0], filt_size[1]),
                                        poolsize=pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[layer+1],
                                        W = None if init_params is None else init_params[param_counter    ] ,
                                        b = None if init_params is None else init_params[param_counter + 1] ,
                                        batch_norm = self.batch_norm,
                                        alpha = None if init_params is None else init_params[param_counter + 2],
                                        p = self.cnn_dropout_rates[layer+1]                                                                                                        
                                         ) )
                                                 
                    conv_layers.append ( 
                                    cnn.Conv2DPoolLayer(
                                        rng = self.rng,
                                        input = conv_layers[layer].output,        
                                        image_shape=(self.batch_size, next_in[2], next_in[0], next_in[1]),
                                        filter_shape=(self.nkerns[layer+1], next_in[2], filt_size[0], filt_size[1]),
                                        poolsize=pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[layer+1],
                                        W = dropout_conv_layers[-1].params[0] ,
                                        b = dropout_conv_layers[-1].params[1],
                                        batch_norm = self.batch_norm, 
                                        alpha = dropout_conv_layers[-1].alpha,
                                        verbose = verbose
                                         ) )                                                       
                                          
                    next_in[0] = int(floor(( next_in[0] - filt_size[0] + 1 ))) / (pool_size[0])      
                    next_in[1] = int(floor(( next_in[1]- filt_size[1] + 1 ))) / (pool_size[1])
                    next_in[2] = self.nkerns[layer+1] / max_out_size
                    
                elif len(filt_size) == 3:
                    dropout_conv_layers.append ( 
                                    cnn.DropoutConv3DPoolLayer(
                                        rng = self.rng,
                                        input = conv_layers[layer].output,        
                                        image_shape=(self.batch_size, next_in[2], stack_size, next_in[0], next_in[1]),
                                        filter_shape=(self.nkerns[layer+1], filt_size[0], stack_size, filt_size[1], filt_size[2]),
                                        poolsize=pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[layer+1],
                                        W = None if init_params is None else init_params[param_counter    ] ,
                                        b = None if init_params is None else init_params[param_counter + 1] ,
                                        batch_norm = self.batch_norm,  
                                        alpha = None if init_params is None else init_params[param_counter + 2],
                                        p = self.cnn_dropout_rates[layer+1]                                                                                                       
                                         ) )                                                                                             
                    conv_layers.append ( 
                                    cnn.Conv3DPoolLayer(
                                        rng = self.rng,
                                        input = conv_layers[layer].output,        
                                        image_shape=(self.batch_size, next_in[2], stack_size, next_in[0], next_in[1]),
                                        filter_shape=(self.nkerns[layer+1], filt_size[0], stack_size, filt_size[1], filt_size[2]),
                                        poolsize=pool_size,
                                        max_out = self.max_out,
                                        maxout_size = max_out_size,
                                        activation = self.cnn_activations[layer+1],
                                        W = dropout_conv_layers[-1].params[0] ,
                                        b = dropout_conv_layers[-1].params[1] ,
                                        batch_norm = self.batch_norm,
                                        alpha = dropout_con_layers[-1].alpha,
                                        verbose = verbose
                                         ) )             
                    next_in[0] = int(floor(( next_in[0] - filt_size[1] + 1 ))) / (pool_size[1] * max_out_size[1])    
                    next_in[1] = int(floor(( next_in[1] - filt_size[2] + 1 ))) / (pool_size[2] * max_out_size [2])
                    next_in[2] = int(floor(self.nkerns[layer+1] * ( next_in[2] - filt_size[0] + 1))) / (pool_size[0] * max_out_size[0])    
                                              
                else:
                    print "!! So far Samosa is only capable of 2D and 3D conv layers."                               
                    sys.exit()
                self.weights.append ( conv_layers[-1].filter_img )
                activity.append( conv_layers[-1].output )

                param_counter = param_counter + 2      
                if self.batch_norm is True:
                    param_counter = param_counter + 1
                    
        # Assemble fully connected laters
        if self.nkerns == []:
            fully_connected_input = first_layer_input.flatten(2)
        else:
            if self.cnn_dropout is False:  # Choose either the dropout path or the without dropout path ... .
                fully_connected_input = conv_layers[-1].output.flatten(2)
            else:
                fully_connected_input = dropout_conv_layers[-1].output.flatten(2)                
    
        if len(self.num_nodes) > 1 :
            layer_sizes =[]                        
            layer_sizes.append( next_in[0] * next_in[1] * next_in[2] )
            
            for i in xrange(len(self.num_nodes)):
                layer_sizes.append ( self.num_nodes[i] )
            layer_sizes.append ( self.outs )
            
        elif self.num_nodes == [] :
            
            layer_sizes = [ next_in[0] * next_in[1] * next_in[2], self.outs]
        elif len(self.num_nodes) ==  1:
            layer_sizes = [ next_in[0] * next_in[1] * next_in[2], self.num_nodes[0] , self.outs]
     
        assert len(layer_sizes) - 2 == len(self.num_nodes)           # Just checking.
    
        """  Dropouts implemented from paper:
        Srivastava, Nitish, et al. "Dropout: A simple way to prevent neural networks
        from overfitting." The Journal of Machine Learning Research 15.1 (2014): 1929-1958.
        """
        MLPlayers = cnn.MLP( rng = self.rng,
                         input = fully_connected_input,
                         layer_sizes = layer_sizes,
                         dropout_rates = self.mlp_dropout_rates,
                         maxout_rates = self.mlp_maxout,
                         max_out = self.max_out, 
                         activations = self.mlp_activations,
                         use_bias = True,
                         svm_flag = self.svm_flag,
                         batch_norm = self.batch_norm, 
                         params = [] if init_params is None else init_params[param_counter:],
                         verbose = verbose)
    
        # create theano functions for evaluating the graph
        # I don't like the idea of having test model only hooked to the test_set_x variable.
        # I would probably have liked to have only one data variable.. but theano tutorials is using 
        # this style, so wth, so will I. 
        self.test_model = theano.function(
                inputs = [index],
                outputs = MLPlayers.errors(y),
                givens={
                    x: self.test_set_x[index * self.batch_size:(index + 1) * self.batch_size],
                    y: self.test_set_y[index * self.batch_size:(index + 1) * self.batch_size]})
    
        self.validate_model = theano.function(
                inputs = [index],
                outputs = MLPlayers.errors(y),
                givens={
                    x: self.valid_set_x[index * self.batch_size:(index + 1) * self.batch_size],
                    y: self.valid_set_y[index * self.batch_size:(index + 1) * self.batch_size]})
    
        self.prediction = theano.function(
            inputs = [index],
            outputs = MLPlayers.predicts,
            givens={
                    x: self.test_set_x[index * self.batch_size: (index + 1) * self.batch_size]})
    
        self.nll = theano.function(
            inputs = [index],
            outputs = MLPlayers.probabilities,
            givens={
                x: self.test_set_x[index * self.batch_size: (index + 1) * self.batch_size]})
    
        # function to return activations of each image
        if not self.nkerns == [] :
            self.activities = theano.function (
                inputs = [index],
                outputs = activity,
                givens = {
                        x: self.train_set_x[index * self.batch_size: (index + 1) * self.batch_size]
                        })
    
        # Compute cost and gradients of the model wrt parameter
        self.params = []
        for layer in conv_layers:
            self.params = self.params + layer.params
            if self.batch_norm is True:
                self.params.append(layer.alpha)
        self.params = self.params + MLPlayers.params
       
        
        # Build the expresson for the categorical cross entropy function.
        if self.svm_flag is False:
            if self.objective == 0:
                cost = MLPlayers.negative_log_likelihood( y )
                dropout_cost = MLPlayers.dropout_negative_log_likelihood( y )
            elif self.objective == 1:
                if len(numpy.unique(self.train_set_y.eval())) > 2:
                    cost = MLPlayers.cross_entropy ( y )
                    dropout_cost = MLPlayers.dropout_cross_entropy ( y )
                else:
                    cost = MLPlayers.binary_entropy ( y )
                    dropout_cost = MLPlayers.dropout_binary_entropy ( y )
            else:
                print "!! Objective is not understood, switching to cross entropy"
                cost = MLPlayers.cross_entropy ( y )
                dropout_cost = MLPlayers.dropout_cross_entropy ( y )
    
        else :        
            cost = MLPlayers.hinge_loss( y1 )
            dropout_cost = MLPlayers.hinge_loss( y1 )
            
            
        output = ( dropout_cost + self.l1_reg * MLPlayers.dropout_L1 + self.l2_reg *
                             MLPlayers.dropout_L2 )if self.mlp_dropout else ( cost + self.l1_reg 
                             * MLPlayers.L1 + self.l2_reg * MLPlayers.L2)
    
        gradients = []      
        for param in self.params: 
            gradient = T.grad( output ,param)
            gradients.append ( gradient )
    
        # TO DO: Try implementing Adadelta also. 
        # Compute momentum for the current epoch
        epoch = T.scalar()
        mom = ifelse(epoch <= self.mom_epoch_interval,
            self.mom_start*(1.0 - epoch/self.mom_epoch_interval) + self.mom_end*(epoch/self.mom_epoch_interval),
            self.mom_end)
    
        # learning rate
        self.eta = theano.shared(numpy.asarray(self.initial_learning_rate,dtype=theano.config.floatX))
        # accumulate gradients for adagrad
         
        grad_acc = []
        for param in self.params:
            eps = numpy.zeros_like(param.get_value(borrow=True), dtype=theano.config.floatX)   
            grad_acc.append(theano.shared(eps, borrow=True))
    
        # accumulate velocities for momentum
        velocities = []
        for param in self.params:
            velocity = theano.shared(numpy.zeros(param.get_value(borrow=True).shape,dtype=theano.config.floatX))
            velocities.append(velocity)
         
    
        # create updates for each combination of stuff 
        updates = OrderedDict()
        print_flag = False
         
        for velocity, gradient, acc , param in zip(velocities, gradients, grad_acc, self.params):        
    
            if self.ada_grad is True:
    
                """ Adagrad implemented from paper:
                John Duchi, Elad Hazan, and Yoram Singer. 2011. Adaptive subgradient methods
                for online learning and stochastic optimization. JMLR
                """
    
                current_acc = acc + T.sqr(gradient) # Accumulates Gradient 
                updates[acc] = current_acc          # updates accumulation at timestamp
    
            elif self.rms_prop is True:
    
                """ Tieleman, T. and Hinton, G. (2012):
                Neural Networks for Machine Learning, Lecture 6.5 - rmsprop.
                Coursera. http://www.youtube.com/watch?v=O3sxAc4hxZU (formula @5:20)"""
    
                current_acc = self.rms_rho * acc + (1 - self.rms_rho) * T.sqr(gradient) 
                updates[acc] = current_acc
    
            else:
                current_acc = 1
                self.fudge_factor = 0
    
            if self.mom_type == 0:               # no momentum
                updates[velocity] = -(self.eta / T.sqrt(current_acc + self.fudge_factor)) * gradient                                            
               
            elif self.mom_type == 1:       # if polyak momentum    
    
                """ Momentum implemented from paper:  
                Polyak, Boris Teodorovich. "Some methods of speeding up the convergence of iteration methods." 
                USSR Computational Mathematics and Mathematical Physics 4.5 (1964): 1-17.
    
                Adapted from Sutskever, Ilya, Hinton et al. "On the importance of initialization and momentum in deep learning." 
                Proceedings of the 30th international conference on machine learning (ICML-13). 2013.
                equation (1) and equation (2)"""   
    
                updates[velocity] = mom * velocity - (1.-mom) * ( self.eta / T.sqrt(current_acc+ self.fudge_factor))  * gradient                             
    
            elif self.mom_type == 2:             # Nestrov accelerated gradient 
    
                """Nesterov, Yurii. "A method of solving a convex programming problem with convergence rate O (1/k2)."
                Soviet Mathematics Doklady. Vol. 27. No. 2. 1983.
                Adapted from https://blogs.princeton.edu/imabandit/2013/04/01/acceleratedgradientdescent/ 
    
                Instead of using past params we use the current params as described in this link
                https://github.com/lisa-lab/pylearn2/pull/136#issuecomment-10381617,"""
      
                updates[velocity] = mom * velocity - (1.-mom) * ( self.eta / T.sqrt(current_acc + self.fudge_factor))  * gradient                                 
                updates[param] = mom * updates[velocity] 
    
            else:
                if print_flag is False:
                    print_flag = True
                    print "!! Unrecognized mometum type, switching to no momentum."
                updates[velocity] = -( self.eta / T.sqrt(current_acc+ self.fudge_factor) ) * gradient                                              
                            
    
            if self.mom_type != 2:
                stepped_param  = param + updates[velocity]
            else:
                stepped_param = param + updates[velocity] + updates[param]
            column_norm = True #This I don't fully understand if its needed after BN is implemented.
            if param.get_value(borrow=True).ndim == 2 and column_norm is True:
    
                """ constrain the norms of the COLUMNs of the weight, according to
                https://github.com/BVLC/caffe/issues/109 """
    
                col_norms = T.sqrt(T.sum(T.sqr(stepped_param), axis=0))
                desired_norms = T.clip(col_norms, 0, T.sqrt(self.squared_filter_length_limit))
                scale = desired_norms / (1e-7 + col_norms)
                updates[param] = stepped_param * scale
    
            else:            
                updates[param] = stepped_param
    
         
        if self.svm_flag is True:
            self.train_model = theano.function(
                    inputs= [index, epoch],
                    outputs = output,
                    updates = updates,
                    givens={
                        x: self.train_set_x[index * self.batch_size:(index + 1) * self.batch_size],
                        y1: self.train_set_y1[index * self.batch_size:(index + 1) * self.batch_size]},
                    on_unused_input = 'ignore'                    
                        )
        else:
            self.train_model = theano.function(
                    inputs = [index, epoch],
                    outputs = output,
                    updates = updates,
                    givens={
                        x: self.train_set_x[index * self.batch_size:(index + 1) * self.batch_size],
                        y: self.train_set_y[index * self.batch_size:(index + 1) * self.batch_size]},
                    on_unused_input='ignore'                    
                        )
    
        self.decay_learning_rate = theano.function(
               inputs=[],          # Just updates the learning rates. 
               updates={self.eta: self.eta * self.learning_rate_decay}
                )
    
        self.momentum_value = theano.function ( 
                            inputs =[epoch],
                            outputs = mom,
                            )
        end_time = time.clock()
        print "...         time taken is " +str(end_time - start_time) + " seconds"
      
                     
    # this is only for self.multi_load = True type of datasets.. 
    # All datasets are not multi_load enabled. This needs to change ??                         
    def reset_data (self, batch, type_set, verbose = True):
        if self.data_type == 'mat':
            data_x, data_y, data_y1 = loaders.load_data_mat(dataset = self.dataset, batch = batch, type_set = type_set, n_classes = self.outs)             

        elif self.data_type == 'skdata':                   
            if self.dataset == 'caltech101':
                data_x, data_y  = loaders.load_skdata_caltech101(
                                                batch_size = self.load_batches, 
                                                batch = batch, 
                                                type_set = type_set, 
                                                rand_perm = self.rand_perm, 
                                                height = self.height, 
                                                width = self.width )
            elif self.dataset == 'caltech256':                  
                data_x, data_y  = loaders.load_skdata_caltech256(
                                                batch_size = self.load_batches, 
                                                batch = batch, 
                                                type_set = type_set, 
                                                rand_perm = self.rand_perm, 
                                                height = self.height, 
                                                width = self.width )
        # Do not use svm_flag for caltech 101   
        
        # If we had used only one datavariable instead of three... this wouldn't have been needed. 
        if type_set == 'train':                             
            self.train_set_x.set_value(data_x ,borrow = True)
            self.train_set_y.set_value(data_y ,borrow = True)                
            if self.svm_flag is True:
                self.train_set_y1.set_value(data_y1, borrow = True)
        elif type_set == 'test':
            self.test_set_x.set_value(data_x ,borrow = True)
            self.test_set_y.set_value(data_y ,borrow = True)                
            if self.svm_flag is True:
                self.test_set_y1.set_value(data_y1, borrow = True)
        else:
            self.valid_set_x.set_value(data_x ,borrow = True)
            self.valid_set_y.set_value(data_y ,borrow = True)                
            if self.svm_flag is True:
                self.valid_set_y1.set_value(data_y1, borrow = True)
        
    def print_net (self, epoch, display_flag = True ):
        # saving down true images. 
        if self.main_img_visual is False:
            for i in xrange( self.n_visual_images):
                curr_img = numpy.asarray(numpy.reshape(self.train_set_x.get_value( borrow = True )
                    [self.visualize_ind[i]],[self.height, self.width, self.channels] ) * 255., dtype='uint8' )
                if self.display_flag is True:
                    cv2.imshow("Image Number " +str(i) + 
                         "_label_" + str(self.train_set_y.eval()[self.visualize_ind[i]]),
                         curr_img)
                cv2.imwrite("../visuals/images/image_" 
                    + str(i)+ "_label_" + str(self.train_set_y.eval()
                    [self.visualize_ind[i]]) + ".jpg", curr_img )
        self.main_img_visual = True

        # visualizing activities.
        activity = self.activities(0)         
        for m in xrange(len(self.nkerns)):   #For each layer 
            loc_ac = '../visuals/activities/layer_' + str(m) + "/epoch_" + str(epoch) +"/"
            if not os.path.exists(loc_ac):   
                os.makedirs(loc_ac)
            current_activity = activity[m]
            for i in xrange(self.n_visual_images):  # for each randomly chosen image .. visualize its activity 
                util.visualize(current_activity[self.visualize_ind[i]], 
                    loc = loc_ac, filename = 'activity_' + str(i) + 
                    "_label_" + str(self.train_set_y.eval()[self.visualize_ind[i]]) +'.jpg' ,
                    show_img = display_flag)

        # visualizing the filters.
        for m in xrange(len(self.nkerns)):
            curr_weights = numpy.squeeze(self.weights[m].eval()) 
            if curr_weights.shape[1] == 3 and len(curr_weights.shape) == 4 and self.color_filter is True:    
            # if the image is color, then first layer looks at color pictures and 
            # I can visualize the filters also as color.
                # import pdb
                # pdb.set_trace()
                curr_image = curr_weights
                if not os.path.exists('../visuals/filters/layer_'+str(m)+'/epoch_'+str(epoch)):
                    os.makedirs('../visuals/filters/layer_'+str(m)+'/epoch_'+str(epoch))
                util.visualize_color_filters(curr_image, loc = '../visuals/filters/layer_' + str(m) + 
                       '/' + 'epoch_' + str(epoch) + '/' , filename = 'kernel_0.jpg' , 
                       show_img = self.display_flag)
            elif len(curr_weights.shape) == 3:
                    if not os.path.exists('../visuals/filters/layer_'+str(m)+'/epoch_'+str(epoch)):
                        os.makedirs('../visuals/filters/layer_'+str(m)+'/epoch_'+str(epoch))
                    util.visualize(curr_weights, loc = '../visuals/filters/layer_' + str(m) + '/' 
                        + 'epoch_' + str(epoch) + '/' , filename = 'kernel_' + 
                        str(i) + '.jpg' , show_img = self.display_flag)
    
            else:       # visualize them as grayscale images.
                for i in xrange(curr_weights.shape[1]):
                    curr_image = curr_weights [:,i,:,:]
                    if not os.path.exists('../visuals/filters/layer_'+str(m)+'/epoch_'+str(epoch)):
                        os.makedirs('../visuals/filters/layer_'+str(m)+'/epoch_'+str(epoch))
                    util.visualize(curr_image, loc = '../visuals/filters/layer_' + str(m) + '/' 
                        + 'epoch_' + str(epoch) + '/' , filename = 'kernel_' + 
                        str(i) + '.jpg' , show_img = self.display_flag)
    
    
    # ToDo: should make a results root dir and put in results there ... like root +'/visuals/' 
    def create_dirs( self, visual_params ):  
        
        self.visualize_flag          = visual_params ["visualize_flag" ]
        self.visualize_after_epochs  = visual_params ["visualize_after_epochs" ]
        self.n_visual_images         = visual_params ["n_visual_images" ] 
        self.display_flag            = visual_params ["display_flag" ]
        self.color_filter            = visual_params ["color_filter" ]
        self.shuffle_batch_ind = numpy.arange(self.batch_size)
        numpy.random.shuffle(self.shuffle_batch_ind)
        self.visualize_ind = self.shuffle_batch_ind[0:self.n_visual_images] 
        # create all directories required for saving results and data.
        if self.visualize_flag is True:
            if not os.path.exists('../visuals'):
                os.makedirs('../visuals')                
            if not os.path.exists('../visuals/activities'):
                os.makedirs('../visuals/activities')
                for i in xrange(len(self.nkerns)):
                    os.makedirs('../visuals/activities/layer_'+str(i))
            if not os.path.exists('../visuals/filters'):
                os.makedirs('../visuals/filters')
                for i in xrange(len(self.nkerns)):
                    os.makedirs('../visuals/filters/layer_'+str(i))
            if not os.path.exists('../visuals/images'):
                os.makedirs('../visuals/images')
        if not os.path.exists('../results/'):
            os.makedirs ('../results')
        
        assert self.batch_size >= self.n_visual_images
        
        
    # TRAIN 
    def train(self, n_epochs, validate_after_epochs, verbose = True):
        print "... training"        
        self.main_img_visual = False
        patience = numpy.inf 
        patience_increase = 2  
        improvement_threshold = 0.995  
        this_validation_loss = []
        best_validation_loss = numpy.inf
        best_iter = 0
        epoch_counter = 0
        early_termination = False
        cost_saved = []
        iteration= 0
        start_time_main = time.clock()
        while (epoch_counter < n_epochs) and (not early_termination):
            epoch_counter = epoch_counter + 1 
             
            start_time = time.clock() 
            for batch in xrange (self.batches2train):
                if verbose is True:
                    print "...          -> epoch: " + str(epoch_counter) + " batch: " + str(batch+1) + " out of " + str(self.batches2train) + " batches"
    
                if self.multi_load is True:
                    iteration= (epoch_counter - 1) * self.n_train_batches * self.batches2train + batch
                    # Load data for this batch
                    self.reset_data ( batch = batch + 1, type_set = 'train' ,verbose = verbose)
                    for minibatch_index in xrange(self.n_train_batches):
                        if verbose is True:
                            print "...                  ->    mini Batch: " + str(minibatch_index + 1) + " out of "    + str(self.n_train_batches)
                        cost_ij = self.train_model( minibatch_index, epoch_counter)
                        cost_saved = cost_saved + [cost_ij]
                        
                else:        
                    iteration= (epoch_counter - 1) * self.n_train_batches + batch
                    cost_ij = self.train_model(batch, epoch_counter)
                    cost_saved = cost_saved +[cost_ij]
             
            if  epoch_counter % validate_after_epochs == 0:  
                validation_losses = 0.   
                if self.multi_load is True:   
                    for batch in xrange ( self.batches2validate ):
                        self.reset_data ( batch = batch + 1, type_set = 'valid' ,verbose = verbose)
                        validation_losses = validation_losses + numpy.sum([[self.validate_model(i) for i in xrange(self.n_valid_batches)]])
                        this_validation_loss = this_validation_loss + [validation_losses]
    
                    if verbose is True:

                        print ("...      -> epoch " + str(epoch_counter) + 
                                         ", cost: " + str(numpy.mean(cost_saved[-1*self.n_train_batches:])) +
                                         ",  validation accuracy :" + str(float( self.batch_size * self.n_valid_batches * self.batches2validate - this_validation_loss[-1])*100
                                                                 /(self.batch_size*self.n_valid_batches*self.batches2validate)) +
                                         "%, learning_rate = " + str(self.eta.get_value(borrow=True))+ 
                                         ", momentum = " +str(self.momentum_value(epoch_counter))  +
                                         " -> best thus far ") if this_validation_loss[-1] < best_validation_loss else ("...      -> epoch " + str(epoch_counter) + 
                                         ", cost: " + str(numpy.mean(cost_saved[-1*self.n_train_batches:])) +
                                         ",  validation accuracy :" + str(float( self.batch_size * self.n_valid_batches * self.batches2validate - this_validation_loss[-1])*100
                                                                 /(self.batch_size*self.n_valid_batches*self.batches2validate)) +
                                         "%, learning_rate = " + str(self.eta.get_value(borrow=True))+ 
                                         ", momentum = " +str(self.momentum_value(epoch_counter)))
                    else:
                       
                        print ("...      -> epoch " + str(epoch_counter) + 
                                         ", cost: " + str(numpy.mean(cost_saved[-1*self.n_train_batches:])) +
                                         ",  validation accuracy :" + str(float( self.batch_size * self.n_valid_batches * self.batches2validate - this_validation_loss[-1])*100
                                                                /(self.batch_size*self.n_valid_batches*self.batches2validate)) + 
                                         "% -> best thus far ") if this_validation_loss[-1] < best_validation_loss else  ("...      -> epoch " + str(epoch_counter) + 
                                         ", cost: " + str(numpy.mean(cost_saved[-1*self.n_train_batches:])) +
                                         ",  validation accuracy :" + str(float( self.batch_size * self.n_valid_batches * self.batches2validate - this_validation_loss[-1])*100
                                                                /(self.batch_size*self.n_valid_batches*self.batches2validate)) + "% ")      
                else: # if not multi_load
    
                    validation_losses = [self.validate_model(i) for i in xrange(self.batches2validate)]
                    this_validation_loss = this_validation_loss + [numpy.sum(validation_losses)]
                    if verbose is True:
                                            
                        print ("...      -> epoch " + str(epoch_counter) + 
                              ", cost: " + str(cost_saved[-1]) +
                              ",  validation accuracy :" + str(float(self.batch_size*self.batches2validate - this_validation_loss[-1])*100
                                                           /(self.batch_size*self.batches2validate)) + 
                              "%, learning_rate = " + str(self.eta.get_value(borrow=True)) + 
                              ", momentum = " +str(self.momentum_value(epoch_counter)) +
                              " -> best thus far ") if this_validation_loss[-1] < best_validation_loss else ("...      -> epoch " + str(epoch_counter) + 
                              ", cost: " + str(cost_saved[-1]) +
                              ",  validation accuracy :" + str(float(self.batch_size*self.batches2validate - this_validation_loss[-1])*100
                                                           /(self.batch_size*self.batches2validate)) + 
                              "%, learning_rate = " + str(self.eta.get_value(borrow=True)) + 
                              ", momentum = " +str(self.momentum_value(epoch_counter)) )
                    else:
                                
                        print ("...      -> epoch " + str(epoch_counter) + 
                              ", cost: " + str(cost_saved[-1]) +
                              ",  validation accuracy :" + str(float(self.batch_size*self.batches2validate - this_validation_loss[-1])*100
                                                           /(self.batch_size*self.batches2validate)) + 
                              "% -> best thus far ") if this_validation_loss[-1] < best_validation_loss else ("...      -> epoch " + str(epoch_counter) + 
                              ", cost: " + str(cost_saved[-1]) +
                              ",  validation accuracy :" + str(float(self.batch_size*self.batches2validate - this_validation_loss[-1])*100
                                                           /(self.batch_size*self.batches2validate)) + 
                              "% ") 
                       
                # improve patience if loss improvement is good enough
                if this_validation_loss[-1] < best_validation_loss *  \
                   improvement_threshold:
                    patience = max(patience, iteration* patience_increase)
                    best_iter = iteration

                best_validation_loss = min(best_validation_loss, this_validation_loss[-1])
            self.decay_learning_rate()    
    
    
            if self.visualize_flag is True and epoch_counter % self.visualize_after_epochs == 0:
                self.print_net (epoch = epoch_counter, display_flag = self.display_flag)   
            
            end_time = time.clock()
            print "...           time taken for this epoch is " +str((end_time - start_time)) + " seconds"
            
            if patience <= iteration:
                early_termination = True
                break
         
        end_time_main = time.clock()
        print "... time taken for the entire training is " +str((end_time_main - start_time_main)/60) + " minutes"
                    
        # Save down training stuff
        f = open(self.error_file_name,'w')
        for i in xrange(len(this_validation_loss)):
            f.write(str(this_validation_loss[i]))
            f.write("\n")
        f.close()
    
        f = open(self.cost_file_name,'w')
        for i in xrange(len(cost_saved)):
            f.write(str(cost_saved[i]))
            f.write("\n")
        f.close()
    
    def test(self, verbose = True):
        print "... testing"
        start_time = time.clock()
        wrong = 0
        predictions = []
        class_prob = []
        labels = []
         
        if self.multi_load is False:   
            labels = self.test_set_y.eval().tolist()   
            for mini_batch in xrange(self.batches2test):
                #print ".. Testing batch " + str(mini_batch)
                wrong = wrong + int(self.test_model(mini_batch))                        
                predictions = predictions + self.prediction(mini_batch).tolist()
                class_prob = class_prob + self.nll(mini_batch).tolist()
            print ("...      -> total test accuracy : " + str(float((self.batch_size*self.batches2test)-wrong )*100
                                                         /(self.batch_size*self.batches2test)) + 
                         " % out of " + str(self.batch_size*self.batches2test) + " samples.")
                         
        else:           
            for batch in xrange(self.batches2test):
                if verbose is True:
                    print "..       --> testing batch " + str(batch)
                # Load data for this batch
                self.reset_data ( batch = batch + 1, type_set = 'test' ,verbose = verbose)
                labels = labels + self.test_set_y.eval().tolist() 
                for mini_batch in xrange(self.n_test_batches):
                    wrong = wrong + int(self.test_model(mini_batch))   
                    predictions = predictions + self.prediction(mini_batch).tolist()
                    class_prob = class_prob + self.nll(mini_batch).tolist()
             
            print ("...      -> total test accuracy : " + str(float((self.batch_size*self.n_test_batches*self.batches2test)-wrong )*100/
                                                         (self.batch_size*self.n_test_batches*self.batches2test)) + 
                         " % out of " + str(self.batch_size*self.n_test_batches*self.batches2test) + " samples.")
    
        correct = 0 
        confusion = numpy.zeros((self.outs,self.outs), dtype = int)
        for index in xrange(len(predictions)):
            if labels[index] == predictions[index]:
                correct = correct + 1
            confusion[int(predictions[index]),int(labels[index])] = confusion[int(predictions[index]),int(labels[index])] + 1
    
        # Save down data 
        f = open(self.results_file_name, 'w')
        for i in xrange(len(predictions)):
            f.write(str(i))
            f.write("\t")
            f.write(str(labels[i]))
            f.write("\t")
            f.write(str(predictions[i]))
            f.write("\t")
            for j in xrange(self.outs):
                f.write(str(class_prob[i][j]))
                f.write("\t")
            f.write('\n')
        f.close() 

        numpy.savetxt(self.confusion_file_name, confusion, newline="\n")
        print "confusion Matrix with accuracy : " + str(float(correct)/len(predictions)*100) + "%"
        end_time = time.clock()
        print "...         time taken is " +str(end_time - start_time) + " seconds"
            
        if self.visualize_flag is True:    
            print "... saving down the final model's visualizations" 
            self.print_net (epoch = 'final' , display_flag = self.display_flag)     
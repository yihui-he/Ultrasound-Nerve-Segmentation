# create lmdb files 
#-.-encoding=utf-8-.-``
# whenever use Image.open, use 'try'
# convert both raw and mask images into lmdb files
# TODO: Selectively build lmdb with focus

''' 
input: output_train.txt or output_val.txt
output: lmdb dataset files of train or val
NOTE: label has already been resized to their targetedSize, like say 256x256 in this stage 
'''

import matplotlib.pyplot as plt
import caffe
import unet_cfgs as cfgs
# import lmdb
from PIL import Image
import numpy as np
import os
import cv2
import sys
import unet_cfgs as cfgs


debug=False  # for overfitting of 4 images
''' image resizing using PIL'''
def imresize(im,sz):
    pil_im = Image.fromarray(np.uint8(im))
    return np.array(pil_im.resize(sz))


''' ------------------------------------------------- '''  
''' input param '''
input_ = sys.argv[1] #'train'
#input_ = 'val'
data_root = cfgs.lmdb_path
lmdb = 'lmdb_train_val'
''' ------------------------------------------------- '''


''' resize dim '''
sz_data = (cfgs.inShape[1],cfgs.inShape[0]) # image data
sz_mask = (cfgs.inShape[1],cfgs.inShape[0])


''' path '''
save_data_root = os.path.join(data_root, lmdb)
input_lst = input_ + '.txt' # this is a txt file
save_im_lmdb_root = os.path.join(save_data_root, input_ + '_data')
save_mask_lmdb_root = os.path.join(save_data_root, input_ + '_mask')



''' read train or val txt files '''
train_val_list = os.path.join(cfgs.data_list_path, input_lst)
f = open(train_val_list, 'r')
inputs = f.read().splitlines() # read lines in file
f.close()



''' process data lmdb '''
''' ------------------------------------------------- '''
import lmdb
in_db = lmdb.open(save_im_lmdb_root, map_size=int(1e12))

with in_db.begin(write=True) as in_txn:
    # in_idx is indexing number starting from 0; in_ is actually the information
    for in_idx, in_ in enumerate(inputs):              
        if in_idx>3 and debug==True:
            break

        if in_idx%100 == 0: print "%d images have been processed" %in_idx
        path = in_.split(' ')[0]
        try: 
            im = np.array(Image.open(path), dtype=np.float32) # check if opened successfully
        except:
            # print in_
            print 'image is damaged'
            continue
        # print img.shape
        # from psd we get 4-channel image, RGBA
        # im = img[:,:,0:3] # ignore A channel
        im = imresize(im,sz_data) # can't resize it 

        
        # im = im[:,:,::-1] # in BGR (switch from RGB), opencv in the form of BGR
        tmp = np.uint8(np.zeros(im[:,:,np.newaxis].shape))
        tmp[:,:,0]=im
        tmp = tmp.swapaxes(1,2).swapaxes(0,1) # in Channel x Height x Width order (switch from H x W x C)
        im_dat = caffe.io.array_to_datum(tmp) # convert to caffe friendly data format
        # in_idx is the key; im_dat is the value; in_idx keeps track of the lmdb data index
        in_txn.put('{:0>10d}'.format(in_idx), im_dat.SerializeToString())
    
    print '%d images have been processed' %(in_idx+1)

in_db.close()
print 'image lmdb dataset has been created'
''' ------------------------------------------------- '''




''' process mask lmdb'''
''' ------------------------------------------------- '''
in_db = lmdb.open(save_mask_lmdb_root, map_size=int(1e12))

with in_db.begin(write=True) as in_txn:
    for in_idx, in_ in enumerate(inputs):
        if in_idx>3 and debug==True:
            break
            
        if in_idx%100 == 0: print "%d masks have been processed" %in_idx
        path = os.path.join(os.path.dirname(in_).replace('train_data', 'train_mask'), os.path.basename(in_).replace('.tif','_mask.tif')).split(' ')[0] #TODO: replace is a potential bug
        im = np.array(Image.open(path), dtype=np.uint8)

        ''' -------------------------------------------------- '''
        im = imresize(im,sz_mask)
        # label resize function SHOULD NOT be achieved by 'resize' function
        # instead, it must be done by label_down_sample.py 
        ''' -------------------------------------------------- '''

        if debug:
            pass
            cv2.imshow('debug.png', im)
            cv2.waitKey(-1)
        #fit into caffe
        im[im>0]=1
        ''' mask channel is 1 '''
        # since im has only two axis, we need to have 3 axis
        tmp = np.uint8(np.zeros(im[:,:,np.newaxis].shape)) # new a tmp image
        
        # print tmp.shape
        tmp[:,:,0] = im  
        # print tmp.shape
        # in Channel x Height x Width order (switch from H x W x C)
        tmp = tmp.swapaxes(1,2).swapaxes(0,1) 

        im_dat = caffe.proto.caffe_pb2.Datum()
        im_dat.channels = tmp.shape[0]
        im_dat.height = tmp.shape[1]
        im_dat.width = tmp.shape[2]
        im_dat.label = int(in_idx)
        im_dat.data = tmp.tostring()
        in_txn.put('{:0>10d}'.format(in_idx), im_dat.SerializeToString())

    print '%d masks have been processed' %(in_idx+1)

in_db.close()

print 'mask lmdb dataset has been created'
# by yihui
import caffe
from caffe import layers as L, params as P
from caffe.coord_map import crop

def conv_relu(bottom, nout, ks=3, stride=1, pad=1):
    conv = L.Convolution(bottom, kernel_size=ks, stride=stride,
        num_output=nout, pad=pad,
        param=[dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)],
        weight_filler=dict(type='msra'))
    return conv, L.ReLU(conv, in_place=True)

def max_pool(bottom, ks=2, stride=2):
    return L.Pooling(bottom, pool=P.Pooling.MAX, kernel_size=ks, stride=stride)

def fcn(train,mask,batch_size=8):
    n = caffe.NetSpec()
    # n.data, n.sem, n.geo = L.Python(module='siftflow_layers',
    #         layer='SIFTFlowSegDataLayer', ntop=3,
    #         param_str=str(dict(siftflow_dir='../data/sift-flow',
    #             split=split, seed=1337)))

    n.data =L.Data(backend=P.Data.LMDB,batch_size=batch_size, source=train,
                             transform_param=dict(scale=1./255),ntop=1
                  )

    n.geo = L.Data(backend=P.Data.LMDB, batch_size=batch_size, source=mask,
                         ntop=1)
    # the base net
    n.conv1_1, n.relu1_1 = conv_relu(n.data, 64,pad=100)
    n.conv1_2, n.relu1_2 = conv_relu(n.relu1_1, 64)
    n.pool1 = max_pool(n.relu1_2)

    n.conv2_1, n.relu2_1 = conv_relu(n.pool1, 128)
    n.conv2_2, n.relu2_2 = conv_relu(n.relu2_1, 128)
    n.pool2 = max_pool(n.relu2_2)

    n.conv3_1, n.relu3_1 = conv_relu(n.pool2, 256)
    n.conv3_2, n.relu3_2 = conv_relu(n.relu3_1, 256)
    n.conv3_3, n.relu3_3 = conv_relu(n.relu3_2, 256)
    n.pool3 = max_pool(n.relu3_3)

    n.conv4_1, n.relu4_1 = conv_relu(n.pool3, 512)
    n.conv4_2, n.relu4_2 = conv_relu(n.relu4_1, 512)
    n.conv4_3, n.relu4_3 = conv_relu(n.relu4_2, 512)
    n.pool4 = max_pool(n.relu4_3)

    n.conv5_1, n.relu5_1 = conv_relu(n.pool4, 512)
    n.conv5_2, n.relu5_2 = conv_relu(n.relu5_1, 512)
    n.conv5_3, n.relu5_3 = conv_relu(n.relu5_2, 512)
    n.pool5 = max_pool(n.relu5_3)

    # fully conv

    dropout=True
    Deconv_filters=300
    if dropout:
        n.fc6, n.relu6 = conv_relu(n.pool5, 4096, ks=7, pad=0)
        n.drop6 = L.Dropout(n.relu6, dropout_ratio=0.5, in_place=True)
        n.fc7, n.relu7 = conv_relu(n.drop6, 4096, ks=1, pad=0)
        n.drop7 = L.Dropout(n.relu7, dropout_ratio=0.5, in_place=True)
        n.score_fr_geo = L.Convolution(n.drop7, num_output=Deconv_filters, kernel_size=1, pad=0,
            param=[dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)])
    else:
        n.fc6, n.relu6 = conv_relu(n.pool5, 4096, ks=7, pad=0)
        n.fc7, n.relu7 = conv_relu(n.relu6, 4096, ks=1, pad=0)
    # upsampling
        n.score_fr_geo = L.Convolution(n.relu7, num_output=Deconv_filters, kernel_size=1, pad=0,
        param=[dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)])

    n.upscore2_geo = L.Deconvolution(n.score_fr_geo,
        convolution_param=dict(num_output=Deconv_filters, kernel_size=4, stride=2,
            bias_term=False,
            weight_filler=dict(type="msra")
            ),
        param=[dict(lr_mult=0)],
        )

    n.score_pool4_geo = L.Convolution(n.pool4, num_output=Deconv_filters, kernel_size=1, pad=0,
        param=[dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)])
    n.score_pool4_geoc = crop(n.score_pool4_geo, n.upscore2_geo)
    n.fuse_pool4_geo = L.Eltwise(n.upscore2_geo, n.score_pool4_geoc,
            operation=P.Eltwise.SUM)
    n.upscore_pool4_geo  = L.Deconvolution(n.fuse_pool4_geo,
        convolution_param=dict(num_output=Deconv_filters, kernel_size=4, stride=2,
            bias_term=False,
            weight_filler=dict(type="msra")
            ),
        param=[dict(lr_mult=0)])

    n.score_pool3_geo = L.Convolution(n.pool3, num_output=Deconv_filters, kernel_size=1,
            pad=0, param=[dict(lr_mult=1, decay_mult=1), dict(lr_mult=2,
                decay_mult=0)])
    n.score_pool3_geoc = crop(n.score_pool3_geo, n.upscore_pool4_geo)
    n.fuse_pool3_geo = L.Eltwise(n.upscore_pool4_geo, n.score_pool3_geoc,
            operation=P.Eltwise.SUM)
    n.upscore8_geo = L.Deconvolution(n.fuse_pool3_geo,
        convolution_param=dict(num_output=Deconv_filters, kernel_size=16, stride=8,#ks 16
            bias_term=False,
            weight_filler=dict(type="msra")
            ),
        param=[dict(lr_mult=0)])

    b=L.Convolution(n.upscore8_geo, kernel_size=3, stride=1,
        num_output=2, pad=1,
        param=[dict(lr_mult=1, decay_mult=1), dict(lr_mult=2, decay_mult=0)],
        weight_filler=dict(type='msra'))

    n.score_geo = max_pool(crop(b, n.data))
    #n.score_geo = max_pool(crop(n.upscore8_geo, n.data))

    n.loss_geo = L.SoftmaxWithLoss(n.score_geo, n.geo,
            loss_param=dict(normalize=False))#, ignore_label=255))

    return n.to_proto()

def make_net():
    with open('trainval.prototxt', 'w') as f:
        f.write(str(fcn('/mnt/data1/yihuihe/selected_data/gen_shantian12_pos_and_neg/lmdb_train_val/train_data','/mnt/data1/yihuihe/selected_data/gen_shantian12_pos_and_neg/lmdb_train_val/train_mask')))

    with open('test.prototxt', 'w') as f:
        f.write(str(fcn('/mnt/data1/yihuihe/selected_data/gen_shantian12_pos_and_neg/lmdb_train_val/val_data','/mnt/data1/yihuihe/selected_data/gen_shantian12_pos_and_neg/lmdb_train_val/val_mask',1)))

if __name__ == '__main__':
    make_net()

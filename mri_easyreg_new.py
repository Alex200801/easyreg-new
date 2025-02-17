import os
import argparse
import numpy as np
import voxelmorph as vxm
import torch
import surfa as sf
import nibabel as nib
from scipy.ndimage import gaussian_filter, binary_dilation, binary_erosion, distance_transform_edt, binary_fill_holes
from scipy.ndimage import label as scipy_label

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import tensorflow as tf
import keras
import keras.backend as K
import keras.layers as KL


# set tensorflow logging
tf.get_logger().setLevel('ERROR')
K.set_image_data_format('channels_last')


def main():

    parser = argparse.ArgumentParser(description="EasyReg: deep learning registration simple and easy", epilog='\n')

    # input/outputs
    parser.add_argument("--ref", help="Reference image .")
    parser.add_argument("--ref_seg", help="Reference SynthSeg segmentation (will be created if it does not exist).")
    parser.add_argument("--flo", help="Floating image.")
    parser.add_argument("--flo_seg", help="Floating SynthSeg segmentation (will be created if it does not exist).")
    parser.add_argument("--ref_reg", help="(optional) Registered referenced.")
    parser.add_argument("--flo_reg", help="(optional) Registetred floating images (in space of reference).")
    parser.add_argument("--fwd_field", help="(optional) Forward field")
    parser.add_argument("--bak_field", help="(optional) Inverse field")
    parser.add_argument("--affine_only", action="store_true", help="(optional) Skips nonlinear part")
    parser.add_argument("--autocrop", action="store_true", help="(optional) Ignore background voxels in FOV.")
    parser.add_argument("--threads", type=int, default=1, help="(optional) Number of cores to be used. Default is 1. You can use -1 to use all available cores")

    # parse commandline
    main_args = parser.parse_args()

    with open(main_args.ref, 'r') as file:
        all_ref_files = []
        for line in file:
            all_ref_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.flo, 'r') as file:
        all_flo_files = []
        for line in file:
            all_flo_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.ref_seg, 'r') as file:
        all_ref_seg_files = []
        for line in file:
            all_ref_seg_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.flo_seg, 'r') as file:
        all_flo_seg_files = []
        for line in file:
            all_flo_seg_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.ref_reg, 'r') as file:
        all_ref_reg_files = []
        for line in file:
            all_ref_reg_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.flo_reg, 'r') as file:
        all_flo_reg_files = []
        for line in file:
            all_flo_reg_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.fwd_field, 'r') as file:
        all_fwd_field_files = []
        for line in file:
            all_fwd_field_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters

    with open(main_args.bak_field, 'r') as file:
        all_bak_field_files = []
        for line in file:
            all_bak_field_files.append(line.strip())  # .strip() removes any extra whitespace/newline characters
            
    assert len(all_ref_files) == len(all_flo_files), "Length mismatch"
    assert len(all_ref_files) == len(all_ref_seg_files), "Length mismatch"
    assert len(all_ref_files) == len(all_flo_seg_files), "Length mismatch"
    assert len(all_ref_files) == len(all_ref_reg_files), "Length mismatch"
    assert len(all_ref_files) == len(all_flo_reg_files), "Length mismatch"
    assert len(all_ref_files) == len(all_fwd_field_files), "Length mismatch"
    assert len(all_ref_files) == len(all_bak_field_files), "Length mismatch"

    for pat_i in range(len(all_ref_files)):

	
        print("now doing", pat_i, all_ref_files[pat_i])
        parser_i = argparse.ArgumentParser(description="EasyReg: deep learning registration simple and easy", epilog='\n')

        # input/outputs
        parser_i.add_argument("--ref", help="Reference image .")
        parser_i.add_argument("--ref_seg", help="Reference SynthSeg segmentation (will be created if it does not exist).")
        parser_i.add_argument("--flo", help="Floating image.")
        parser_i.add_argument("--flo_seg", help="Floating SynthSeg segmentation (will be created if it does not exist).")
        parser_i.add_argument("--ref_reg", help="(optional) Registered referenced.")
        parser_i.add_argument("--flo_reg", help="(optional) Registetred floating images (in space of reference).")
        parser_i.add_argument("--fwd_field", help="(optional) Forward field")
        parser_i.add_argument("--bak_field", help="(optional) Inverse field")
        parser_i.add_argument("--affine_only", action="store_true", help="(optional) Skips nonlinear part")
        parser_i.add_argument("--autocrop", action="store_true", help="(optional) Ignore background voxels in FOV.")
        parser_i.add_argument("--threads", type=int, default=1, help="(optional) Number of cores to be used. Default is 1. You can use -1 to use all available cores")

        # Simulate command-line arguments
        args = parser_i.parse_args(["--ref", all_ref_files[pat_i],
                                    "--flo", all_flo_files[pat_i],
                                    "--ref_seg", all_ref_seg_files[pat_i],
                                    "--flo_seg", all_flo_seg_files[pat_i],
                                    "--ref_reg", all_ref_reg_files[pat_i],
                                    "--flo_reg", all_flo_reg_files[pat_i],
                                    "--fwd_field", all_fwd_field_files[pat_i],
                                    "--bak_field", all_bak_field_files[pat_i]])

        #############

        # Very first thing: we require FreeSurfer
        if not os.environ.get('FREESURFER_HOME'):
            sf.system.fatal('FREESURFER_HOME is not set. Please source freesurfer.')
        fs_home = os.environ.get('FREESURFER_HOME')

        if args.ref is None:
            sf.system.fatal('Reference image must be provided')
        if args.flo is None:
            sf.system.fatal('Floating image must be provided')
        if args.ref_seg is None:
            sf.system.fatal('Reference segmentation must be provided')
        if args.flo_seg is None:
            sf.system.fatal('Floating segmentation must be provided')
        if (args.ref_reg is None) and (args.flo_reg is None) and (args.fwd_field is None) and (args.bak_field is None):
            sf.system.fatal('Please provide at least one of: registered reference, registered floating, forward field, or backward field')

        # limit the number of threads to be used if running on CPU
        if args.threads == 1:
            print('using 1 thread')
        elif args.threads<0:
            args.threads = os.cpu_count()
            print('using all available threads ( %s )' % args.threads)
        else:
            print('using %s threads' % args.threads)
        tf.config.threading.set_inter_op_parallelism_threads(args.threads)
        tf.config.threading.set_intra_op_parallelism_threads(args.threads)
        torch.set_num_threads(args.threads)

        # path models
        path_model_segmentation = fs_home + '/models/synthseg_2.0.h5'
        path_model_parcellation = fs_home + '/models/synthseg_parc_2.0.h5'
        path_model_registration_trained = fs_home + '/models/easyreg_v10_230103.h5'

        # path labels
        labels_segmentation = fs_home +  '/models/synthseg_segmentation_labels_2.0.npy'
        labels_parcellation = fs_home +  '/models/synthseg_parcellation_labels.npy'
        atlas_volsize = [160, 160, 192]
        atlas_aff = np.matrix([[-1, 0, 0, 79], [0, 0, 1, -104], [0, -1, 0, 79], [0, 0, 0, 1]])

        # get label lists
        labels_segmentation, _ = get_list_labels(label_list=labels_segmentation)
        labels_segmentation, unique_idx = np.unique(labels_segmentation, return_index=True)
        labels_parcellation, _ = np.unique(get_list_labels(labels_parcellation)[0], return_index=True)

        # Segment if needed
        if (args.ref_seg is not None) and os.path.exists(args.ref_seg):
            print('Segmentation of reference image already exists; reading from disk')
            ref_seg_buffer, ref_seg_aff, ref_h = load_volume(args.ref_seg, im_only=False, squeeze=True, dtype=None, aff_ref=None)
            if np.sum(ref_seg_buffer>1000)==0:
                sf.system.fatal('No cortical labels found; does the segmentation include cortical parcels?')
            segmentation_net = None
            # even nearest neighbour interpolation can cause issues with matching labels,
            # so we need to handle the segmentation values
            if np.issubdtype( ref_seg_buffer.dtype, float ):
                ref_seg_buffer = np.round(ref_seg_buffer).astype(int)
        else:
            print('Segmenting reference image')
            print('   Reading reference image')
            ref_image, ref_aff, ref_h, ref_im_res, ref_shape, ref_pad_idx, ref_crop_idx = preprocess(path_image=args.ref,
                                                                                                     crop=None, min_pad=128,
                                                                                                     path_resample=None,
                                                                                                     autocrop=args.autocrop)
            print('   Setting up segmentation net')
            segmentation_net = build_seg_model(model_file_segmentation=path_model_segmentation,
                                               model_file_parcellation=path_model_parcellation,
                                               labels_segmentation=labels_segmentation,
                                               labels_parcellation=labels_parcellation)
            print('   Inference / segmentation')
            post_patch_segmentation, post_patch_parcellation = segmentation_net.predict(ref_image)
            print('   Postprocessing')
            ref_seg_buffer, _, _ = postprocess(post_patch_seg=post_patch_segmentation,
                                               post_patch_parc=post_patch_parcellation,
                                               shape=ref_shape,
                                               pad_idx=ref_pad_idx,
                                               crop_idx=ref_crop_idx,
                                               labels_segmentation=labels_segmentation,
                                               labels_parcellation=labels_parcellation,
                                               aff=ref_aff,
                                               im_res=ref_im_res)
            print('   Saving result')
            ref_seg_aff = ref_aff
            save_volume(ref_seg_buffer, ref_seg_aff, ref_h, args.ref_seg, dtype='int32')

        if (args.flo_seg is not None) and os.path.exists(args.flo_seg):
            print('Segmentation of floating image already exists; reading from disk')
            flo_seg_buffer, flo_seg_aff, flo_h = load_volume(args.flo_seg, im_only=False, squeeze=True, dtype=None, aff_ref=None)
            if np.sum(flo_seg_buffer>1000)==0:
                sf.system.fatal('No cortical labels found; does the segmentation include cortical parcels?')
            # even nearest neighbour interpolation can cause issues with matching labels,
            # so we need to handle the segmentation values
            if np.issubdtype( flo_seg_buffer.dtype, float ):
                flo_seg_buffer = np.round(flo_seg_buffer).astype(int)
        else:
            print('Segmenting floating image')
            print('   Reading floating image')
            flo_image, flo_aff, flo_h, flo_im_res, flo_shape, ref_pad_idx, ref_crop_idx = preprocess(path_image=args.flo,
                                                                                                     crop=None, min_pad=128,
                                                                                                     path_resample=None,
                                                                                                     autocrop=args.autocrop)
            if segmentation_net is None:
                print('   Setting up segmentation net')
                segmentation_net = build_seg_model(model_file_segmentation=path_model_segmentation,
                                                   model_file_parcellation=path_model_parcellation,
                                                   labels_segmentation=labels_segmentation,
                                                   labels_parcellation=labels_parcellation)
            print('   Inference / segmentation')
            post_patch_segmentation, post_patch_parcellation = segmentation_net.predict(flo_image)
            print('   Postprocessing')
            flo_seg_buffer, _, _ = postprocess(post_patch_seg=post_patch_segmentation,
                                               post_patch_parc=post_patch_parcellation,
                                               shape=flo_shape,
                                               pad_idx=ref_pad_idx,
                                               crop_idx=ref_crop_idx,
                                               labels_segmentation=labels_segmentation,
                                               labels_parcellation=labels_parcellation,
                                               aff=flo_aff,
                                               im_res=flo_im_res)
            print('   Saving result')
            flo_seg_aff = flo_aff
            save_volume(flo_seg_buffer, flo_seg_aff, flo_h, args.flo_seg, dtype='int32')

        # Now the linear registration part
        print('Linear registration')

        print('  Computing centroids and estimating affine transform')
        labels = np.array([2,4,5,7,8,10,11,12,13,14,15,16,17,18,26,28,41,43,44,46,47,49,50,51,52,53,54,58,60,
                                        1001,1002,1003,1005,1006,1007,1008,1009,1010,1011,1012,1013,1014,1015,1016,1017,1018,1019,1020,1021,1022,1023,1024,1025,1026,1027,1028,1029,1030,1031,1032,1033,1034,1035,
                                        2001,2002,2003,2005,2006,2007,2008,2009,2010,2011,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025,2026,2027,2028,2029,2030,2031,2032,2033,2034,2035])
        nlab = len(labels)
        atlasCOG = np.array([[-28.,-18.,-37.,-19.,-27.,-19.,-23.,-31.,-26.,-2.,-3.,-3.,-29.,-26.,-14.,-14.,24.,14.,31.,12.,18.,14.,19.,26.,21.,25.,22.,11.,8.,-52.,-6.,-36.,-7.,-24.,-37.,-39.,-52.,-9.,-27.,-26.,-14.,-8.,-59.,-28.,-7.,-49.,-43.,-47.,-12.,-46.,-6.,-43.,-10.,-7.,-33.,-11.,-23.,-55.,-50.,-10.,-29.,-46.,-38.,48.,4.,31.,3.,21.,33.,37.,47.,3.,24.,20.,8.,4.,54.,21.,5.,45.,38.,46.,8.,45.,3.,38.,6.,4.,29.,9.,19.,51.,49.,10.,24.,43.,33.],
                            [-30.,-17.,-13.,-36.,-40.,-22.,-3.,-5.,-9.,-14.,-31.,-21.,-15.,-1.,3.,-16.,-32.,-20.,-14.,-37.,-42.,-24.,-3.,-6.,-10.,-15.,-2.,3.,-17.,-44.,-5.,-15.,-71.,2.,-29.,-70.,-23.,-44.,-73.,22.,-57.,27.,-19.,-23.,-45.,4.,31.,20.,-68.,-38.,-33.,-26.,-60.,23.,22.,0.,-72.,-12.,-49.,49.,17.,-25.,-3.,-42.,-1.,-16.,-76.,0.,-34.,-69.,-16.,-44.,-73.,22.,-56.,28.,-18.,-25.,-45.,-3.,30.,14.,-69.,-37.,-32.,-30.,-60.,21.,21.,0.,-72.,-11.,-49.,48.,15.,-27.,-3.],
                            [12.,14.,-13.,-41.,-51.,1.,13.,3.,1.,0.,-40.,-28.,-15.,-10.,2.,-7.,11.,14.,-12.,-40.,-51.,2.,14.,4.,2.,-14.,-10.,4.,-7.,-8.,32.,40.,-14.,-21.,-28.,-4.,-28.,-3.,-35.,3.,-29.,4.,-17.,-21.,35.,18.,9.,20.,-24.,28.,25.,34.,7.,18.,35.,48.,16.,-5.,12.,22.,-18.,1.,4.,-12.,32.,43.,-11.,-21.,-29.,-3.,-27.,0.,-34.,3.,-25.,6.,-18.,-20.,36.,18.,11.,20.,-20.,26.,25.,34.,4.,24.,34.,47.,17.,-5.,10.,20.,-18.,0.,4.]])

        refCOG = np.zeros([4, nlab])
        ok = np.ones(nlab)
        for l in range(nlab):
            aux = np.where(ref_seg_buffer == labels[l])
            if len(aux[0]) > 50:
                refCOG[0, l] = np.median(aux[0])
                refCOG[1, l] = np.median(aux[1])
                refCOG[2, l] = np.median(aux[2])
                refCOG[3, l] = 1
            else:
                ok[l] = 0
        refCOG = np.matmul(ref_seg_aff, refCOG)[:-1, :]
        Mref = getM(atlasCOG[:, ok > 0], refCOG[:, ok > 0])

        floCOG = np.zeros([4, nlab])
        ok = np.ones(nlab)
        for l in range(nlab):
            aux = np.where(flo_seg_buffer == labels[l])
            if len(aux[0]) > 50:
                floCOG[0, l] = np.median(aux[0])
                floCOG[1, l] = np.median(aux[1])
                floCOG[2, l] = np.median(aux[2])
                floCOG[3, l] = 1
            else:
                ok[l] = 0
        floCOG = np.matmul(flo_seg_aff, floCOG)[:-1, :]
        Mflo = getM(atlasCOG[:, ok > 0], floCOG[:, ok > 0])

        print('  Reading reference image')
        R, Raff, Rh = load_volume(args.ref, im_only=False, squeeze=True, dtype=None, aff_ref=None)
        R = torch.tensor(R, device='cpu')
        print('  Deforming reference image to reference space')
        II, JJ, KK = np.meshgrid(np.arange(atlas_volsize[0]), np.arange(atlas_volsize[1]), np.arange(atlas_volsize[2]), indexing='ij')
        II = torch.tensor(II, device='cpu')
        JJ = torch.tensor(JJ, device='cpu')
        KK = torch.tensor(KK, device='cpu')
        affine = torch.tensor(np.matmul(np.linalg.inv(Raff), np.matmul(Mref, atlas_aff)), device='cpu')
        II2 = affine[0, 0] * II + affine[0, 1] * JJ + affine[0, 2] * KK + affine[0, 3]
        JJ2 = affine[1, 0] * II + affine[1, 1] * JJ + affine[1, 2] * KK + affine[1, 3]
        KK2 = affine[2, 0] * II + affine[2, 1] * JJ + affine[2, 2] * KK + affine[2, 3]
        Rlin = fast_3D_interp_torch(R, II2, JJ2, KK2, 'linear')

        print('  Deforming reference segmentation to reference space')
        affine = torch.tensor(np.matmul(np.linalg.inv(ref_seg_aff), np.matmul(Mref, atlas_aff)), device='cpu')
        II2 = affine[0, 0] * II + affine[0, 1] * JJ + affine[0, 2] * KK + affine[0, 3]
        JJ2 = affine[1, 0] * II + affine[1, 1] * JJ + affine[1, 2] * KK + affine[1, 3]
        KK2 = affine[2, 0] * II + affine[2, 1] * JJ + affine[2, 2] * KK + affine[2, 3]
        RSlin = fast_3D_interp_torch(torch.tensor(ref_seg_buffer.copy(), device='cpu'), II2, JJ2, KK2, 'nearest')

        print('  Normalizing intensities of reference image')
        Rlin[RSlin == 0] = 0
        Rlin = Rlin / torch.max(Rlin)

        print('  Reading floating image')
        F, Faff, Fh = load_volume(args.flo, im_only=False, squeeze=True, dtype=None, aff_ref=None)
        F = torch.tensor(F, device='cpu')
        print('  Deforming floating image to reference space')
        affine = torch.tensor(np.matmul(np.linalg.inv(Faff), np.matmul(Mflo, atlas_aff)), device='cpu')
        II2 = affine[0, 0] * II + affine[0, 1] * JJ + affine[0, 2] * KK + affine[0, 3]
        JJ2 = affine[1, 0] * II + affine[1, 1] * JJ + affine[1, 2] * KK + affine[1, 3]
        KK2 = affine[2, 0] * II + affine[2, 1] * JJ + affine[2, 2] * KK + affine[2, 3]
        Flin = fast_3D_interp_torch(F, II2, JJ2, KK2, 'linear')

        print('  Deforming floating segmentation to reference space')
        affine = torch.tensor(np.matmul(np.linalg.inv(flo_seg_aff), np.matmul(Mflo, atlas_aff)), device='cpu')
        II2 = affine[0, 0] * II + affine[0, 1] * JJ + affine[0, 2] * KK + affine[0, 3]
        JJ2 = affine[1, 0] * II + affine[1, 1] * JJ + affine[1, 2] * KK + affine[1, 3]
        KK2 = affine[2, 0] * II + affine[2, 1] * JJ + affine[2, 2] * KK + affine[2, 3]
        FSlin = fast_3D_interp_torch(torch.tensor(flo_seg_buffer.copy(), device='cpu'), II2, JJ2, KK2, 'nearest')

        print('  Normalizing intensities of floating image')
        Flin[FSlin == 0] = 0
        Flin = Flin / torch.max(Flin)

        # Now the nonlinear registration part (if needed)
        if args.affine_only:
            print('Skipping nonlinear registration')

        else:

            source = tf.keras.Input(shape=(*atlas_volsize, 1))
            target = tf.keras.Input(shape=(*atlas_volsize, 1))

            config = {'name': 'vxm_dense', 'fill_value': None, 'input_model': None, 'unet_half_res': True, 'trg_feats': 1,
             'src_feats': 1, 'use_probs': False, 'bidir': False, 'int_downsize': 2, 'int_steps': 10,
             'nb_unet_conv_per_level': 1, 'unet_feat_mult': 1, 'nb_unet_levels': None,
             'nb_unet_features': [[256, 256, 256, 256], [256, 256, 256, 256, 256, 256]], 'inshape': atlas_volsize}
            cnn = vxm.networks.VxmDense(**config)
            cnn.load_weights(path_model_registration_trained, by_name=True)
            svf1 = cnn([source, target])[1]
            svf2 = cnn([target, source])[1]
            pos_svf = KL.Lambda(lambda x: 0.5 * x[0] - 0.5 * x[1])([svf1, svf2])
            neg_svf = KL.Lambda(lambda x: -x)(pos_svf)
            pos_def_small = vxm.layers.VecInt(method='ss', int_steps=10)(pos_svf)
            neg_def_small = vxm.layers.VecInt(method='ss', int_steps=10)(neg_svf)
            pos_def = vxm.layers.RescaleTransform(2)(pos_def_small)
            neg_def = vxm.layers.RescaleTransform(2)(neg_def_small)
            model = tf.keras.Model(inputs=[source, target],
                                          outputs=[pos_def, neg_def])
            model.load_weights(path_model_registration_trained)

            pred = model.predict([Rlin.detach().numpy()[np.newaxis, ..., np.newaxis], Flin.detach().numpy()[np.newaxis, ..., np.newaxis]])

            r2f_field = torch.tensor(np.squeeze(pred[0]))
            f2r_field = torch.tensor(np.squeeze(pred[1]))

        # concatenate transforms and save outputs
        print('Deforming and writing to disk')

        if (args.fwd_field is not None) or (args.flo_reg is not None):
            print('  Computing forward field')
            II, JJ, KK = np.meshgrid(np.arange(R.shape[0]), np.arange(R.shape[1]), np.arange(R.shape[2]), indexing='ij')
            II = torch.tensor(II, device='cpu')
            JJ = torch.tensor(JJ, device='cpu')
            KK = torch.tensor(KK, device='cpu')
            affine = torch.tensor(np.matmul(np.linalg.inv(atlas_aff), np.matmul(np.linalg.inv(Mref), Raff)), device='cpu')
            II2 = affine[0, 0] * II + affine[0, 1] * JJ + affine[0, 2] * KK + affine[0, 3]
            JJ2 = affine[1, 0] * II + affine[1, 1] * JJ + affine[1, 2] * KK + affine[1, 3]
            KK2 = affine[2, 0] * II + affine[2, 1] * JJ + affine[2, 2] * KK + affine[2, 3]
            if args.affine_only:
                II3 = II2
                JJ3 = JJ2
                KK3 = KK2
            else:
                FIELD = fast_3D_interp_field_torch(f2r_field, II2, JJ2, KK2)
                II3 = II2 + FIELD[:, :, :, 0]
                JJ3 = JJ2 + FIELD[:, :, :, 1]
                KK3 = KK2 + FIELD[:, :, :, 2]
            affine = torch.tensor(np.matmul(Mflo, atlas_aff), device='cpu')
            RAS_X = affine[0, 0] * II3 + affine[0, 1] * JJ3 + affine[0, 2] * KK3 + affine[0, 3]
            RAS_Y = affine[1, 0] * II3 + affine[1, 1] * JJ3 + affine[1, 2] * KK3 + affine[1, 3]
            RAS_Z = affine[2, 0] * II3 + affine[2, 1] * JJ3 + affine[2, 2] * KK3 + affine[2, 3]
            if args.fwd_field is not None:
                print('  Saving forward field')
                save_volume(torch.stack([RAS_X, RAS_Y, RAS_Z], axis=-1), Raff, Rh, args.fwd_field, n_dims=3)
            if args.flo_reg is not None:
                print('  Deforming floating image')
                affine = torch.tensor(np.linalg.inv(Faff), device='cpu')
                II4 = affine[0, 0] * RAS_X + affine[0, 1] * RAS_Y + affine[0, 2] * RAS_Z + affine[0, 3]
                JJ4 = affine[1, 0] * RAS_X + affine[1, 1] * RAS_Y + affine[1, 2] * RAS_Z + affine[1, 3]
                KK4 = affine[2, 0] * RAS_X + affine[2, 1] * RAS_Y + affine[2, 2] * RAS_Z + affine[2, 3]
                registered = fast_3D_interp_torch(F, II4, JJ4, KK4, 'linear')
                print('  Saving deformed floating image')
                save_volume(registered, Raff, Rh, args.flo_reg)

        if (args.bak_field is not None) or (args.ref_reg is not None):
            print('  Computing backward field')
            II, JJ, KK = np.meshgrid(np.arange(F.shape[0]), np.arange(F.shape[1]), np.arange(F.shape[2]), indexing='ij')
            II = torch.tensor(II, device='cpu')
            JJ = torch.tensor(JJ, device='cpu')
            KK = torch.tensor(KK, device='cpu')
            affine = torch.tensor(np.matmul(np.linalg.inv(atlas_aff), np.matmul(np.linalg.inv(Mflo), Faff)), device='cpu')
            II2 = affine[0, 0] * II + affine[0, 1] * JJ + affine[0, 2] * KK + affine[0, 3]
            JJ2 = affine[1, 0] * II + affine[1, 1] * JJ + affine[1, 2] * KK + affine[1, 3]
            KK2 = affine[2, 0] * II + affine[2, 1] * JJ + affine[2, 2] * KK + affine[2, 3]
            if args.affine_only:
                II3 = II2
                JJ3 = JJ2
                KK3 = KK2
            else:
                FIELD = fast_3D_interp_field_torch(r2f_field, II2, JJ2, KK2)
                II3 = II2 + FIELD[:, :, :, 0]
                JJ3 = JJ2 + FIELD[:, :, :, 1]
                KK3 = KK2 + FIELD[:, :, :, 2]
            affine = torch.tensor(np.matmul(Mref, atlas_aff), device='cpu')
            RAS_X = affine[0, 0] * II3 + affine[0, 1] * JJ3 + affine[0, 2] * KK3 + affine[0, 3]
            RAS_Y = affine[1, 0] * II3 + affine[1, 1] * JJ3 + affine[1, 2] * KK3 + affine[1, 3]
            RAS_Z = affine[2, 0] * II3 + affine[2, 1] * JJ3 + affine[2, 2] * KK3 + affine[2, 3]
            if args.bak_field is not None:
                print('  Saving backward field')
                save_volume(torch.stack([RAS_X, RAS_Y, RAS_Z], axis=-1), Faff, Fh, args.bak_field, n_dims=3)
            if args.ref_reg is not None:
                print('  Deforming reference image')
                affine = torch.tensor(np.linalg.inv(Raff), device='cpu')
                II4 = affine[0, 0] * RAS_X + affine[0, 1] * RAS_Y + affine[0, 2] * RAS_Z + affine[0, 3]
                JJ4 = affine[1, 0] * RAS_X + affine[1, 1] * RAS_Y + affine[1, 2] * RAS_Z + affine[1, 3]
                KK4 = affine[2, 0] * RAS_X + affine[2, 1] * RAS_Y + affine[2, 2] * RAS_Z + affine[2, 3]
                registered = fast_3D_interp_torch(R, II4, JJ4, KK4, 'linear')
                print('  Saving deformed reference image')
                save_volume(registered, Faff, Fh, args.ref_reg)

        print('All done')
        print(' ')
        print('If you use EasyReg in your analysis, please cite:')
        print('A ready-to-use machine learning tool for symmetric multi-modality registration of brain MRI.')
        print('JE Iglesias. Scientific Reports, accepted for publication.')
        print('https://www.nature.com/articles/s41598-023-33781-0')
        print(' ')


#######################
# Auxiliary functions #
#######################


def get_list_labels(label_list=None, save_label_list=None, FS_sort=False):

    # load label list if previously computed
    label_list = np.array(reformat_to_list(label_list, load_as_numpy=True, dtype='int'))


    # sort labels in neutral/left/right according to FS labels
    n_neutral_labels = 0
    if FS_sort:
        neutral_FS_labels = [0, 14, 15, 16, 21, 22, 23, 24, 72, 77, 80, 85, 100, 101, 102, 103, 104, 105, 106, 107, 108,
                             109, 165, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210,
                             251, 252, 253, 254, 255, 258, 259, 260, 331, 332, 333, 334, 335, 336, 337, 338, 339, 340,
                             502, 506, 507, 508, 509, 511, 512, 514, 515, 516, 517, 530,
                             531, 532, 533, 534, 535, 536, 537]
        neutral = list()
        left = list()
        right = list()
        for la in label_list:
            if la in neutral_FS_labels:
                if la not in neutral:
                    neutral.append(la)
            elif (0 < la < 14) | (16 < la < 21) | (24 < la < 40) | (135 < la < 139) | (1000 <= la <= 1035) | \
                    (la == 865) | (20100 < la < 20110):
                if la not in left:
                    left.append(la)
            elif (39 < la < 72) | (162 < la < 165) | (2000 <= la <= 2035) | (20000 < la < 20010) | (la == 139) | \
                    (la == 866):
                if la not in right:
                    right.append(la)
            else:
                raise Exception('label {} not in our current FS classification, '
                                'please update get_list_labels in utils.py'.format(la))
        label_list = np.concatenate([sorted(neutral), sorted(left), sorted(right)])
        if ((len(left) > 0) & (len(right) > 0)) | ((len(left) == 0) & (len(right) == 0)):
            n_neutral_labels = len(neutral)
        else:
            n_neutral_labels = len(label_list)

    # save labels if specified
    if save_label_list is not None:
        np.save(save_label_list, np.int32(label_list))

    if FS_sort:
        return np.int32(label_list), n_neutral_labels
    else:
        return np.int32(label_list), None

def reformat_to_list(var, length=None, load_as_numpy=False, dtype=None):
    # convert to list
    if var is None:
        return None
    var = load_array_if_path(var, load_as_numpy=load_as_numpy)
    if isinstance(var, (int, float, np.int8, np.int16, np.int32, np.int64, np.float16, np.float32, np.float64)):
        var = [var]
    elif isinstance(var, tuple):
        var = list(var)
    elif isinstance(var, np.ndarray):
        if var.shape == (1,):
            var = [var[0]]
        else:
            var = np.squeeze(var).tolist()
    elif isinstance(var, str):
        var = [var]
    elif isinstance(var, bool):
        var = [var]
    if isinstance(var, list):
        if length is not None:
            if len(var) == 1:
                var = var * length
            elif len(var) != length:
                raise ValueError('if var is a list/tuple/numpy array, it should be of length 1 or {0}, '
                                 'had {1}'.format(length, var))
    else:
        raise TypeError('var should be an int, float, tuple, list, numpy array, or path to numpy array')

    # convert items type
    if dtype is not None:
        if dtype == 'int':
            var = [int(v) for v in var]
        elif dtype == 'float':
            var = [float(v) for v in var]
        elif dtype == 'bool':
            var = [bool(v) for v in var]
        elif dtype == 'str':
            var = [str(v) for v in var]
        else:
            raise ValueError("dtype should be 'str', 'float', 'int', or 'bool'; had {}".format(dtype))
    return var

def load_array_if_path(var, load_as_numpy=True):
    if (isinstance(var, str)) & load_as_numpy:
        assert os.path.isfile(var), 'No such path: %s' % var
        var = np.load(var)
    return var


def load_volume(path_volume, im_only=True, squeeze=True, dtype=None, aff_ref=None):

    assert path_volume.endswith(('.nii', '.nii.gz', '.mgz', '.npz')), 'Unknown data file: %s' % path_volume

    if path_volume.endswith(('.nii', '.nii.gz', '.mgz')):
        x = nib.load(path_volume)
        if squeeze:
            volume = np.squeeze(x.get_fdata())
        else:
            volume = x.get_fdata()
        aff = x.affine
        header = x.header
    else:  # npz
        volume = np.load(path_volume)['vol_data']
        if squeeze:
            volume = np.squeeze(volume)
        aff = np.eye(4)
        header = nib.Nifti1Header()
    if dtype is not None:
        if 'int' in dtype:
            volume = np.round(volume)
        volume = volume.astype(dtype=dtype)

    # align image to reference affine matrix
    if aff_ref is not None:
        n_dims, _ = get_dims(list(volume.shape), max_channels=10)
        volume, aff = align_volume_to_ref(volume, aff, aff_ref=aff_ref, return_aff=True, n_dims=n_dims)

    if im_only:
        return volume
    else:
        return volume, aff, header




def preprocess(path_image, n_levels=5, crop=None, min_pad=None, path_resample=None, autocrop=False):
    # read image and corresponding info
    im, _, aff, n_dims, n_channels, h, im_res = get_volume_info(path_image, True)
    if n_dims < 3:
        sf.system.fatal('input should have 3 dimensions, had %s' % n_dims)
    elif n_dims == 4 and n_channels == 1:
        n_dims = 3
        im = im[..., 0]
    elif n_dims > 3:
        sf.system.fatal('input should have 3 dimensions, had %s' % n_dims)
    elif n_channels > 1:
        print('WARNING: detected more than 1 channel, only keeping the first channel.')
        im = im[..., 0]

    # resample image if necessary
    if np.any((im_res > 1.05) | (im_res < 0.95)):
        im_res = np.array([1.] * 3)
        im, aff = resample_volume(im, aff, im_res)
        if path_resample is not None:
            save_volume(im, aff, h, path_resample)

    # align image
    im = align_volume_to_ref(im, aff, aff_ref=np.eye(4), n_dims=n_dims, return_copy=False)
    shape = list(im.shape[:n_dims])

    # crop image if necessary
    if crop is not None:
        crop = reformat_to_list(crop, length=n_dims, dtype='int')
        crop_shape = [find_closest_number_divisible_by_m(s, 2 ** n_levels, 'higher') for s in crop]
        im, crop_idx = crop_volume(im, cropping_shape=crop_shape, return_crop_idx=True)
    else:
        crop_idx = None

    # normalise image
    im = rescale_volume(im, new_min=0, new_max=1, min_percentile=0.5, max_percentile=99.5)

    # automatically crop out obvious background
    if autocrop and crop_idx is None:
        nz_locs = np.argwhere(im > 0)
        min_indices = np.min(nz_locs, axis=0)
        max_indices = np.max(nz_locs, axis=0)
        nz_crop = max_indices - min_indices + 2
        crop_shape = [find_closest_number_divisible_by_m(s, 2 ** n_levels, 'higher') for s in nz_crop]
        half_dim_diff = np.floor_divide([crop_shape[i] - nz_crop[i] for i in range(n_dims)], 2)
        min_crop_idx = np.maximum(min_indices - half_dim_diff, 0)
        max_crop_idx = np.minimum(min_crop_idx + crop_shape, im.shape[:n_dims])
        crop_idx = np.concatenate([np.array(min_crop_idx), np.array(max_crop_idx)])
        if n_dims == 2:
            im = im[crop_idx[0]: crop_idx[2], crop_idx[1]: crop_idx[3], ...]
        elif n_dims == 3:
            im = im[crop_idx[0]: crop_idx[3], crop_idx[1]: crop_idx[4], crop_idx[2]: crop_idx[5], ...]

    # pad image
    input_shape = im.shape[:n_dims]
    pad_shape = [find_closest_number_divisible_by_m(s, 2 ** n_levels, 'higher') for s in input_shape]
    min_pad = reformat_to_list(min_pad, length=n_dims, dtype='int')
    min_pad = [find_closest_number_divisible_by_m(s, 2 ** n_levels, 'higher') for s in min_pad]
    pad_shape = np.maximum(pad_shape, min_pad)
    im, pad_idx = pad_volume(im, padding_shape=pad_shape, return_pad_idx=True)

    # add batch and channel axes
    im = add_axis(im, axis=[0, -1])

    return im, aff, h, im_res, shape, pad_idx, crop_idx


def resample_volume(volume, aff, new_vox_size, interpolation='linear'):
    pixdim = np.sqrt(np.sum(aff * aff, axis=0))[:-1]
    new_vox_size = np.array(new_vox_size)
    factor = pixdim / new_vox_size
    sigmas = 0.25 / factor
    sigmas[factor > 1] = 0  # don't blur if upsampling

    volume_filt = gaussian_filter(volume, sigmas)

    # volume2 = zoom(volume_filt, factor, order=1, mode='reflect', prefilter=False)
    x = np.arange(0, volume_filt.shape[0])
    y = np.arange(0, volume_filt.shape[1])
    z = np.arange(0, volume_filt.shape[2])

    start = - (factor - 1) / (2 * factor)
    step = 1.0 / factor
    stop = start + step * np.ceil(volume_filt.shape * factor)

    xi = np.arange(start=start[0], stop=stop[0], step=step[0])
    yi = np.arange(start=start[1], stop=stop[1], step=step[1])
    zi = np.arange(start=start[2], stop=stop[2], step=step[2])
    xi[xi < 0] = 0
    yi[yi < 0] = 0
    zi[zi < 0] = 0
    xi[xi > (volume_filt.shape[0] - 1)] = volume_filt.shape[0] - 1
    yi[yi > (volume_filt.shape[1] - 1)] = volume_filt.shape[1] - 1
    zi[zi > (volume_filt.shape[2] - 1)] = volume_filt.shape[2] - 1

    xig, yig, zig = np.meshgrid(xi, yi, zi, indexing='ij', sparse=False)
    xig = torch.tensor(xig, device='cpu')
    yig = torch.tensor(yig, device='cpu')
    zig = torch.tensor(zig, device='cpu')
    volume2 = fast_3D_interp_torch(torch.tensor(volume_filt, device='cpu'), xig, yig, zig, 'linear')

    aff2 = aff.copy()
    for c in range(3):
        aff2[:-1, c] = aff2[:-1, c] / factor[c]
    aff2[:-1, -1] = aff2[:-1, -1] - np.matmul(aff2[:-1, :-1], 0.5 * (factor - 1))

    return volume2.numpy(), aff2

def find_closest_number_divisible_by_m(n, m, answer_type='lower'):
    if n % m == 0:
        return n
    else:
        q = int(n / m)
        lower = q * m
        higher = (q + 1) * m
        if answer_type == 'lower':
            return lower
        elif answer_type == 'higher':
            return higher
        elif answer_type == 'closer':
            return lower if (n - lower) < (higher - n) else higher
        else:
            sf.system.fatal('answer_type should be lower, higher, or closer, had : %s' % answer_type)



def get_volume_info(path_volume, return_volume=False, aff_ref=None, max_channels=10):

    im, aff, header = load_volume(path_volume, im_only=False)

    # understand if image is multichannel
    im_shape = list(im.shape)
    n_dims, n_channels = get_dims(im_shape, max_channels=max_channels)
    im_shape = im_shape[:n_dims]

    # get labels res
    if '.nii' in path_volume:
        data_res = np.array(header['pixdim'][1:n_dims + 1])
    elif '.mgz' in path_volume:
        data_res = np.array(header['delta'])  # mgz image
    else:
        data_res = np.array([1.0] * n_dims)

    # align to given affine matrix
    if aff_ref is not None:
        ras_axes = get_ras_axes(aff, n_dims=n_dims)
        ras_axes_ref = get_ras_axes(aff_ref, n_dims=n_dims)
        im = align_volume_to_ref(im, aff, aff_ref=aff_ref, n_dims=n_dims)
        im_shape = np.array(im_shape)
        data_res = np.array(data_res)
        im_shape[ras_axes_ref] = im_shape[ras_axes]
        data_res[ras_axes_ref] = data_res[ras_axes]
        im_shape = im_shape.tolist()

    # return info
    if return_volume:
        return im, im_shape, aff, n_dims, n_channels, header, data_res
    else:
        return im_shape, aff, n_dims, n_channels, header, data_res

def get_dims(shape, max_channels=10):
    if shape[-1] <= max_channels:
        n_dims = len(shape) - 1
        n_channels = shape[-1]
    else:
        n_dims = len(shape)
        n_channels = 1
    return n_dims, n_channels


def get_ras_axes(aff, n_dims=3):
    aff_inverted = np.linalg.inv(aff)
    img_ras_axes = np.argmax(np.absolute(aff_inverted[0:n_dims, 0:n_dims]), axis=0)
    for i in range(n_dims):
        if i not in img_ras_axes:
            unique, counts = np.unique(img_ras_axes, return_counts=True)
            incorrect_value = unique[np.argmax(counts)]
            img_ras_axes[np.where(img_ras_axes == incorrect_value)[0][-1]] = i

    return img_ras_axes

def align_volume_to_ref(volume, aff, aff_ref=None, return_aff=False, n_dims=None, return_copy=True):

    # work on copy
    new_volume = volume.copy() if return_copy else volume
    aff_flo = aff.copy()

    # default value for aff_ref
    if aff_ref is None:
        aff_ref = np.eye(4)

    # extract ras axes
    if n_dims is None:
        n_dims, _ = get_dims(new_volume.shape)
    ras_axes_ref = get_ras_axes(aff_ref, n_dims=n_dims)
    ras_axes_flo = get_ras_axes(aff_flo, n_dims=n_dims)

    # align axes
    aff_flo[:, ras_axes_ref] = aff_flo[:, ras_axes_flo]
    for i in range(n_dims):
        if ras_axes_flo[i] != ras_axes_ref[i]:
            new_volume = np.swapaxes(new_volume, ras_axes_flo[i], ras_axes_ref[i])
            swapped_axis_idx = np.where(ras_axes_flo == ras_axes_ref[i])
            ras_axes_flo[swapped_axis_idx], ras_axes_flo[i] = ras_axes_flo[i], ras_axes_flo[swapped_axis_idx]

    # align directions
    dot_products = np.sum(aff_flo[:3, :3] * aff_ref[:3, :3], axis=0)
    for i in range(n_dims):
        if dot_products[i] < 0:
            new_volume = np.flip(new_volume, axis=i)
            aff_flo[:, i] = - aff_flo[:, i]
            aff_flo[:3, 3] = aff_flo[:3, 3] - aff_flo[:3, i] * (new_volume.shape[i] - 1)

    if return_aff:
        return new_volume, aff_flo
    else:
        return new_volume

def build_seg_model(model_file_segmentation,
                model_file_parcellation,
                labels_segmentation,
                labels_parcellation):

    if not os.path.isfile(model_file_segmentation):
        sf.system.fatal("The provided model path does not exist.")

    # get labels
    n_labels_seg = len(labels_segmentation)

    # build UNet
    net = unet(nb_features=24,
               input_shape=[None, None, None, 1],
               nb_levels=5,
               conv_size=3,
               nb_labels=n_labels_seg,
               feat_mult=2,
               activation='elu',
               nb_conv_per_level=2,
               batch_norm=-1,
               name='unet')
    net.load_weights(model_file_segmentation, by_name=True)
    input_image = net.inputs[0]
    name_segm_prediction_layer = 'unet_prediction'

    # smooth posteriors
    last_tensor = net.output
    last_tensor._keras_shape = tuple(last_tensor.get_shape().as_list())
    last_tensor = GaussianBlur(sigma=0.5)(last_tensor)
    net = keras.Model(inputs=net.inputs, outputs=last_tensor)

    # add aparc segmenter
    n_labels_parcellation = len(labels_parcellation)

    last_tensor = net.output
    last_tensor = KL.Lambda(lambda x: tf.cast(tf.argmax(x, axis=-1), 'int32'))(last_tensor)
    last_tensor = ConvertLabels(np.arange(n_labels_seg), labels_segmentation)(last_tensor)
    parcellation_masking_values = np.array([1 if ((ll == 3) | (ll == 42)) else 0 for ll in labels_segmentation])
    last_tensor = ConvertLabels(labels_segmentation, parcellation_masking_values)(last_tensor)
    last_tensor = KL.Lambda(lambda x: tf.one_hot(tf.cast(x, 'int32'), depth=2, axis=-1))(last_tensor)
    last_tensor = KL.Lambda(lambda x: tf.cast(tf.concat(x, axis=-1), 'float32'))([input_image, last_tensor])
    net = keras.Model(inputs=net.inputs, outputs=last_tensor)

    # build UNet
    net = unet(nb_features=24,
               input_shape=[None, None, None, 3],
               nb_levels=5,
               conv_size=3,
               nb_labels=n_labels_parcellation,
               feat_mult=2,
               activation='elu',
               nb_conv_per_level=2,
               batch_norm=-1,
               name='unet_parc',
               input_model=net)
    net.load_weights(model_file_parcellation, by_name=True)

    # smooth predictions
    last_tensor = net.output
    last_tensor._keras_shape = tuple(last_tensor.get_shape().as_list())
    last_tensor = GaussianBlur(sigma=0.5)(last_tensor)
    net = keras.Model(inputs=net.inputs, outputs=[net.get_layer(name_segm_prediction_layer).output, last_tensor])

    return net

def unet(nb_features,
         input_shape,
         nb_levels,
         conv_size,
         nb_labels,
         name='unet',
         prefix=None,
         feat_mult=1,
         pool_size=2,
         padding='same',
         dilation_rate_mult=1,
         activation='elu',
         skip_n_concatenations=0,
         use_residuals=False,
         final_pred_activation='softmax',
         nb_conv_per_level=1,
         layer_nb_feats=None,
         conv_dropout=0,
         batch_norm=None,
         input_model=None):

    # naming
    model_name = name
    if prefix is None:
        prefix = model_name

    # volume size data
    ndims = len(input_shape) - 1
    if isinstance(pool_size, int):
        pool_size = (pool_size,) * ndims

    # get encoding model
    enc_model = conv_enc(nb_features,
                         input_shape,
                         nb_levels,
                         conv_size,
                         name=model_name,
                         prefix=prefix,
                         feat_mult=feat_mult,
                         pool_size=pool_size,
                         padding=padding,
                         dilation_rate_mult=dilation_rate_mult,
                         activation=activation,
                         use_residuals=use_residuals,
                         nb_conv_per_level=nb_conv_per_level,
                         layer_nb_feats=layer_nb_feats,
                         conv_dropout=conv_dropout,
                         batch_norm=batch_norm,
                         input_model=input_model)

    # get decoder
    # use_skip_connections=True makes it a u-net
    lnf = layer_nb_feats[(nb_levels * nb_conv_per_level):] if layer_nb_feats is not None else None
    dec_model = conv_dec(nb_features,
                         None,
                         nb_levels,
                         conv_size,
                         nb_labels,
                         name=model_name,
                         prefix=prefix,
                         feat_mult=feat_mult,
                         pool_size=pool_size,
                         use_skip_connections=True,
                         skip_n_concatenations=skip_n_concatenations,
                         padding=padding,
                         dilation_rate_mult=dilation_rate_mult,
                         activation=activation,
                         use_residuals=use_residuals,
                         final_pred_activation=final_pred_activation,
                         nb_conv_per_level=nb_conv_per_level,
                         batch_norm=batch_norm,
                         layer_nb_feats=lnf,
                         conv_dropout=conv_dropout,
                         input_model=enc_model)
    final_model = dec_model

    return final_model

def conv_enc(nb_features,
             input_shape,
             nb_levels,
             conv_size,
             name=None,
             prefix=None,
             feat_mult=1,
             pool_size=2,
             dilation_rate_mult=1,
             padding='same',
             activation='elu',
             layer_nb_feats=None,
             use_residuals=False,
             nb_conv_per_level=2,
             conv_dropout=0,
             batch_norm=None,
             input_model=None):

    # naming
    model_name = name
    if prefix is None:
        prefix = model_name

    # first layer: input
    name = '%s_input' % prefix
    if input_model is None:
        input_tensor = KL.Input(shape=input_shape, name=name)
        last_tensor = input_tensor
    else:
        input_tensor = input_model.inputs
        last_tensor = input_model.outputs
        if isinstance(last_tensor, list):
            last_tensor = last_tensor[0]

    # volume size data
    ndims = len(input_shape) - 1
    if isinstance(pool_size, int):
        pool_size = (pool_size,) * ndims

    # prepare layers
    convL = getattr(KL, 'Conv%dD' % ndims)
    conv_kwargs = {'padding': padding, 'activation': activation, 'data_format': 'channels_last'}
    maxpool = getattr(KL, 'MaxPooling%dD' % ndims)

    # down arm:
    # add nb_levels of conv + ReLu + conv + ReLu. Pool after each of first nb_levels - 1 layers
    lfidx = 0  # level feature index
    for level in range(nb_levels):
        lvl_first_tensor = last_tensor
        nb_lvl_feats = np.round(nb_features * feat_mult ** level).astype(int)
        conv_kwargs['dilation_rate'] = dilation_rate_mult ** level

        for conv in range(nb_conv_per_level):  # does several conv per level, max pooling applied at the end
            if layer_nb_feats is not None:  # None or List of all the feature numbers
                nb_lvl_feats = layer_nb_feats[lfidx]
                lfidx += 1

            name = '%s_conv_downarm_%d_%d' % (prefix, level, conv)
            if conv < (nb_conv_per_level - 1) or (not use_residuals):
                last_tensor = convL(nb_lvl_feats, conv_size, **conv_kwargs, name=name)(last_tensor)
            else:  # no activation
                last_tensor = convL(nb_lvl_feats, conv_size, padding=padding, name=name)(last_tensor)

            if conv_dropout > 0:
                # conv dropout along feature space only
                name = '%s_dropout_downarm_%d_%d' % (prefix, level, conv)
                noise_shape = [None, *[1] * ndims, nb_lvl_feats]
                last_tensor = KL.Dropout(conv_dropout, noise_shape=noise_shape, name=name)(last_tensor)

        if use_residuals:
            convarm_layer = last_tensor

            # the "add" layer is the original input
            # However, it may not have the right number of features to be added
            nb_feats_in = lvl_first_tensor.get_shape()[-1]
            nb_feats_out = convarm_layer.get_shape()[-1]
            add_layer = lvl_first_tensor
            if nb_feats_in > 1 and nb_feats_out > 1 and (nb_feats_in != nb_feats_out):
                name = '%s_expand_down_merge_%d' % (prefix, level)
                last_tensor = convL(nb_lvl_feats, conv_size, **conv_kwargs, name=name)(lvl_first_tensor)
                add_layer = last_tensor

                if conv_dropout > 0:
                    name = '%s_dropout_down_merge_%d_%d' % (prefix, level, conv)
                    noise_shape = [None, *[1] * ndims, nb_lvl_feats]

            name = '%s_res_down_merge_%d' % (prefix, level)
            last_tensor = KL.add([add_layer, convarm_layer], name=name)

            name = '%s_res_down_merge_act_%d' % (prefix, level)
            last_tensor = KL.Activation(activation, name=name)(last_tensor)

        if batch_norm is not None:
            name = '%s_bn_down_%d' % (prefix, level)
            last_tensor = KL.BatchNormalization(axis=batch_norm, name=name, fused=False)(last_tensor)

        # max pool if we're not at the last level
        if level < (nb_levels - 1):
            name = '%s_maxpool_%d' % (prefix, level)
            last_tensor = maxpool(pool_size=pool_size, name=name, padding=padding)(last_tensor)

    # create the model and return
    model = keras.Model(inputs=input_tensor, outputs=[last_tensor], name=model_name)
    return model


def conv_dec(nb_features,
             input_shape,
             nb_levels,
             conv_size,
             nb_labels,
             name=None,
             prefix=None,
             feat_mult=1,
             pool_size=2,
             use_skip_connections=False,
             skip_n_concatenations=0,
             padding='same',
             dilation_rate_mult=1,
             activation='elu',
             use_residuals=False,
             final_pred_activation='softmax',
             nb_conv_per_level=2,
             layer_nb_feats=None,
             batch_norm=None,
             conv_dropout=0,
             input_model=None):

    # naming
    model_name = name
    if prefix is None:
        prefix = model_name

    # if using skip connections, make sure need to use them.
    if use_skip_connections:
        assert input_model is not None, "is using skip connections, tensors dictionary is required"

    # first layer: input
    input_name = '%s_input' % prefix
    if input_model is None:
        input_tensor = KL.Input(shape=input_shape, name=input_name)
        last_tensor = input_tensor
    else:
        input_tensor = input_model.input
        last_tensor = input_model.output
        input_shape = last_tensor.shape.as_list()[1:]

    # vol size info
    ndims = len(input_shape) - 1
    if isinstance(pool_size, int):
        if ndims > 1:
            pool_size = (pool_size,) * ndims

    # prepare layers
    convL = getattr(KL, 'Conv%dD' % ndims)
    conv_kwargs = {'padding': padding, 'activation': activation}
    upsample = getattr(KL, 'UpSampling%dD' % ndims)

    # up arm:
    # nb_levels - 1 layers of Deconvolution3D
    #    (approx via up + conv + ReLu) + merge + conv + ReLu + conv + ReLu
    lfidx = 0
    for level in range(nb_levels - 1):
        nb_lvl_feats = np.round(nb_features * feat_mult ** (nb_levels - 2 - level)).astype(int)
        conv_kwargs['dilation_rate'] = dilation_rate_mult ** (nb_levels - 2 - level)

        # upsample matching the max pooling layers size
        name = '%s_up_%d' % (prefix, nb_levels + level)
        last_tensor = upsample(size=pool_size, name=name)(last_tensor)
        up_tensor = last_tensor

        # merge layers combining previous layer
        if use_skip_connections & (level < (nb_levels - skip_n_concatenations - 1)):
            conv_name = '%s_conv_downarm_%d_%d' % (prefix, nb_levels - 2 - level, nb_conv_per_level - 1)
            cat_tensor = input_model.get_layer(conv_name).output
            name = '%s_merge_%d' % (prefix, nb_levels + level)
            last_tensor = KL.concatenate([cat_tensor, last_tensor], axis=ndims + 1, name=name)

        # convolution layers
        for conv in range(nb_conv_per_level):
            if layer_nb_feats is not None:
                nb_lvl_feats = layer_nb_feats[lfidx]
                lfidx += 1

            name = '%s_conv_uparm_%d_%d' % (prefix, nb_levels + level, conv)
            if conv < (nb_conv_per_level - 1) or (not use_residuals):
                last_tensor = convL(nb_lvl_feats, conv_size, **conv_kwargs, name=name)(last_tensor)
            else:
                last_tensor = convL(nb_lvl_feats, conv_size, padding=padding, name=name)(last_tensor)

            if conv_dropout > 0:
                name = '%s_dropout_uparm_%d_%d' % (prefix, level, conv)
                noise_shape = [None, *[1] * ndims, nb_lvl_feats]
                last_tensor = KL.Dropout(conv_dropout, noise_shape=noise_shape, name=name)(last_tensor)

        # residual block
        if use_residuals:

            # the "add" layer is the original input
            # However, it may not have the right number of features to be added
            add_layer = up_tensor
            nb_feats_in = add_layer.get_shape()[-1]
            nb_feats_out = last_tensor.get_shape()[-1]
            if nb_feats_in > 1 and nb_feats_out > 1 and (nb_feats_in != nb_feats_out):
                name = '%s_expand_up_merge_%d' % (prefix, level)
                add_layer = convL(nb_lvl_feats, conv_size, **conv_kwargs, name=name)(add_layer)

                if conv_dropout > 0:
                    name = '%s_dropout_up_merge_%d_%d' % (prefix, level, conv)
                    noise_shape = [None, *[1] * ndims, nb_lvl_feats]
                    last_tensor = KL.Dropout(conv_dropout, noise_shape=noise_shape, name=name)(last_tensor)

            name = '%s_res_up_merge_%d' % (prefix, level)
            last_tensor = KL.add([last_tensor, add_layer], name=name)

            name = '%s_res_up_merge_act_%d' % (prefix, level)
            last_tensor = KL.Activation(activation, name=name)(last_tensor)

        if batch_norm is not None:
            name = '%s_bn_up_%d' % (prefix, level)
            last_tensor = KL.BatchNormalization(axis=batch_norm, name=name, fused=False)(last_tensor)

    # Compute likelyhood prediction (no activation yet)
    name = '%s_likelihood' % prefix
    last_tensor = convL(nb_labels, 1, activation=None, name=name)(last_tensor)
    like_tensor = last_tensor

    # output prediction layer
    # we use a softmax to compute P(L_x|I) where x is each location
    if final_pred_activation == 'softmax':
        name = '%s_prediction' % prefix
        softmax_lambda_fcn = lambda x: keras.activations.softmax(x, axis=ndims + 1)
        pred_tensor = KL.Lambda(softmax_lambda_fcn, name=name)(last_tensor)

    # otherwise create a layer that does nothing.
    else:
        name = '%s_prediction' % prefix
        pred_tensor = KL.Activation('linear', name=name)(like_tensor)

    # create the model and retun
    model = keras.Model(inputs=input_tensor, outputs=pred_tensor, name=model_name)
    return model

def postprocess(post_patch_seg, post_patch_parc, shape, pad_idx, crop_idx,
                labels_segmentation, labels_parcellation, aff, im_res):

    # get posteriors
    post_patch_seg = np.squeeze(post_patch_seg)
    post_patch_seg = crop_volume_with_idx(post_patch_seg, pad_idx, n_dims=3, return_copy=False)

    # keep biggest connected component
    tmp_post_patch_seg = post_patch_seg[..., 1:]
    post_patch_seg_mask = np.sum(tmp_post_patch_seg, axis=-1) > 0.25
    post_patch_seg_mask = get_largest_connected_component(post_patch_seg_mask)
    post_patch_seg_mask = np.stack([post_patch_seg_mask]*tmp_post_patch_seg.shape[-1], axis=-1)
    tmp_post_patch_seg = mask_volume(tmp_post_patch_seg, mask=post_patch_seg_mask, return_copy=False)
    post_patch_seg[..., 1:] = tmp_post_patch_seg

    # reset posteriors to zero outside the largest connected component of each topological class
    post_patch_seg_mask = post_patch_seg > 0.2
    post_patch_seg[..., 1:] *= post_patch_seg_mask[..., 1:]

    # get hard segmentation
    post_patch_seg /= np.sum(post_patch_seg, axis=-1)[..., np.newaxis]
    seg_patch = labels_segmentation[post_patch_seg.argmax(-1).astype('int32')].astype('int32')

    # postprocess parcellation
    post_patch_parc = np.squeeze(post_patch_parc)
    post_patch_parc = crop_volume_with_idx(post_patch_parc, pad_idx, n_dims=3, return_copy=False)
    mask = (seg_patch == 3) | (seg_patch == 42)
    post_patch_parc[..., 0] = np.ones_like(post_patch_parc[..., 0])
    post_patch_parc[..., 0] = mask_volume(post_patch_parc[..., 0], mask=mask < 0.1, return_copy=False)
    post_patch_parc /= np.sum(post_patch_parc, axis=-1)[..., np.newaxis]
    parc_patch = labels_parcellation[post_patch_parc.argmax(-1).astype('int32')].astype('int32')
    seg_patch[mask] = parc_patch[mask]

    # paste patches back to matrix of original image size
    if crop_idx is not None:
        # we need to go through this because of the posteriors of the background, otherwise pad_volume would work
        seg = np.zeros(shape=shape, dtype='int32')
        posteriors = np.zeros(shape=[*shape, labels_segmentation.shape[0]])
        posteriors[..., 0] = np.ones(shape)  # place background around patch
        seg[crop_idx[0]:crop_idx[3], crop_idx[1]:crop_idx[4], crop_idx[2]:crop_idx[5]] = seg_patch
        posteriors[crop_idx[0]:crop_idx[3], crop_idx[1]:crop_idx[4], crop_idx[2]:crop_idx[5], :] = post_patch_seg
    else:
        seg = seg_patch
        posteriors = post_patch_seg

    # align prediction back to first orientation
    seg = align_volume_to_ref(seg, aff=np.eye(4), aff_ref=aff, n_dims=3, return_copy=False)
    posteriors = align_volume_to_ref(posteriors, np.eye(4), aff_ref=aff, n_dims=3, return_copy=False)

    # compute volumes
    volumes = np.sum(posteriors[..., 1:], axis=tuple(range(0, len(posteriors.shape) - 1)))
    volumes = np.concatenate([np.array([np.sum(volumes)]), volumes])
    if post_patch_parc is not None:
        volumes_parc = np.sum(post_patch_parc[..., 1:], axis=tuple(range(0, len(posteriors.shape) - 1)))
        total_volume_cortex = np.sum(volumes[np.where((labels_segmentation == 3) | (labels_segmentation == 42))[0] - 1])
        volumes_parc = volumes_parc / np.sum(volumes_parc) * total_volume_cortex
        volumes = np.concatenate([volumes, volumes_parc])
    volumes = np.around(volumes * np.prod(im_res), 3)

    return seg, posteriors, volumes

def save_volume(volume, aff, header, path, res=None, dtype=None, n_dims=3):
    mkdir(os.path.dirname(path))
    if '.npz' in path:
        np.savez_compressed(path, vol_data=volume)
    else:
        if header is None:
            header = nib.Nifti1Header()
        if isinstance(aff, str):
            if aff == 'FS':
                aff = np.array([[-1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
        elif aff is None:
            aff = np.eye(4)
        nifty = nib.Nifti1Image(volume, aff, header)
        if dtype is not None:
            if 'int' in dtype:
                volume = np.round(volume)
            volume = volume.astype(dtype=dtype)
            nifty.set_data_dtype(dtype)
        if res is not None:
            if n_dims is None:
                n_dims, _ = get_dims(volume.shape)
            res = reformat_to_list(res, length=n_dims, dtype=None)
            nifty.header.set_zooms(res)
        nib.save(nifty, path)



def mkdir(path_dir):

    if len(path_dir)>0:
        if path_dir[-1] == '/':
            path_dir = path_dir[:-1]
        if not os.path.isdir(path_dir):
            list_dir_to_create = [path_dir]
            while not os.path.isdir(os.path.dirname(list_dir_to_create[-1])):
                list_dir_to_create.append(os.path.dirname(list_dir_to_create[-1]))
            for dir_to_create in reversed(list_dir_to_create):
                os.mkdir(dir_to_create)


def getM(ref, mov):

    zmat = np.zeros(ref.shape[::-1])
    zcol = np.zeros([ref.shape[1], 1])
    ocol = np.ones([ref.shape[1], 1])
    zero = np.zeros(zmat.shape)

    A = np.concatenate([
        np.concatenate([np.transpose(ref), zero, zero, ocol, zcol, zcol], axis=1),
        np.concatenate([zero, np.transpose(ref), zero, zcol, ocol, zcol], axis=1),
        np.concatenate([zero, zero, np.transpose(ref), zcol, zcol, ocol], axis=1)], axis=0)

    b = np.concatenate([np.transpose(mov[0, :]), np.transpose(mov[1, :]), np.transpose(mov[2, :])], axis=0)

    x = np.matmul(np.linalg.inv(np.matmul(np.transpose(A), A)), np.matmul(np.transpose(A), b))

    M = np.stack([
        [x[0], x[1], x[2], x[9]],
        [x[3], x[4], x[5], x[10]],
        [x[6], x[7], x[8], x[11]],
        [0, 0, 0, 1]])

    return M


def fast_3D_interp_torch(X, II, JJ, KK, mode):
    if mode=='nearest':
        IIr = torch.round(II).long()
        JJr = torch.round(JJ).long()
        KKr = torch.round(KK).long()
        IIr[IIr < 0] = 0
        JJr[JJr < 0] = 0
        KKr[KKr < 0] = 0
        IIr[IIr > (X.shape[0] - 1)] = (X.shape[0] - 1)
        JJr[JJr > (X.shape[1] - 1)] = (X.shape[1] - 1)
        KKr[KKr > (X.shape[2] - 1)] = (X.shape[2] - 1)
        Y = X[IIr, JJr, KKr]
    elif mode=='linear':
        ok = (II>0) & (JJ>0) & (KK>0) & (II<=X.shape[0]-1) & (JJ<=X.shape[1]-1) & (KK<=X.shape[2]-1)
        IIv = II[ok]
        JJv = JJ[ok]
        KKv = KK[ok]

        fx = torch.floor(IIv).long()
        cx = fx + 1
        cx[cx > (X.shape[0] - 1)] = (X.shape[0] - 1)
        wcx = IIv - fx
        wfx = 1 - wcx

        fy = torch.floor(JJv).long()
        cy = fy + 1
        cy[cy > (X.shape[1] - 1)] = (X.shape[1] - 1)
        wcy = JJv - fy
        wfy = 1 - wcy

        fz = torch.floor(KKv).long()
        cz = fz + 1
        cz[cz > (X.shape[2] - 1)] = (X.shape[2] - 1)
        wcz = KKv - fz
        wfz = 1 - wcz

        c000 = X[fx, fy, fz]
        c100 = X[cx, fy, fz]
        c010 = X[fx, cy, fz]
        c110 = X[cx, cy, fz]
        c001 = X[fx, fy, cz]
        c101 = X[cx, fy, cz]
        c011 = X[fx, cy, cz]
        c111 = X[cx, cy, cz]

        c00 = c000 * wfx + c100 * wcx
        c01 = c001 * wfx + c101 * wcx
        c10 = c010 * wfx + c110 * wcx
        c11 = c011 * wfx + c111 * wcx

        c0 = c00 * wfy + c10 * wcy
        c1 = c01 * wfy + c11 * wcy

        c = c0 * wfz + c1 * wcz

        Y = torch.zeros(II.shape, device='cpu')
        Y[ok] = c.float()

    else:
        sf.system.fatal('mode must be linear or nearest')

    return Y



def fast_3D_interp_field_torch(X, II, JJ, KK):

    ok = (II > 0) & (JJ > 0) & (KK > 0) & (II <= X.shape[0] - 1) & (JJ <= X.shape[1] - 1) & (KK <= X.shape[2] - 1)
    IIv = II[ok]
    JJv = JJ[ok]
    KKv = KK[ok]

    fx = torch.floor(IIv).long()
    cx = fx + 1
    cx[cx > (X.shape[0] - 1)] = (X.shape[0] - 1)
    wcx = IIv - fx
    wfx = 1 - wcx

    fy = torch.floor(JJv).long()
    cy = fy + 1
    cy[cy > (X.shape[1] - 1)] = (X.shape[1] - 1)
    wcy = JJv - fy
    wfy = 1 - wcy

    fz = torch.floor(KKv).long()
    cz = fz + 1
    cz[cz > (X.shape[2] - 1)] = (X.shape[2] - 1)
    wcz = KKv - fz
    wfz = 1 - wcz

    Y = torch.zeros([*II.shape, 3], device='cpu')
    for channel in range(3):

        Xc = X[:, :, :, channel]

        c000 = Xc[fx, fy, fz]
        c100 = Xc[cx, fy, fz]
        c010 = Xc[fx, cy, fz]
        c110 = Xc[cx, cy, fz]
        c001 = Xc[fx, fy, cz]
        c101 = Xc[cx, fy, cz]
        c011 = Xc[fx, cy, cz]
        c111 = Xc[cx, cy, cz]

        c00 = c000 * wfx + c100 * wcx
        c01 = c001 * wfx + c101 * wcx
        c10 = c010 * wfx + c110 * wcx
        c11 = c011 * wfx + c111 * wcx

        c0 = c00 * wfy + c10 * wcy
        c1 = c01 * wfy + c11 * wcy

        c = c0 * wfz + c1 * wcz

        Yc = torch.zeros(II.shape, device='cpu')
        Yc[ok] = c.float()

        Y[:, :, :, channel] = Yc

    return Y


def crop_volume_with_idx(volume, crop_idx, aff=None, n_dims=None, return_copy=True):

    # get info
    new_volume = volume.copy() if return_copy else volume
    n_dims = int(np.array(crop_idx).shape[0] / 2) if n_dims is None else n_dims

    # crop image
    if n_dims == 2:
        new_volume = new_volume[crop_idx[0]:crop_idx[2], crop_idx[1]:crop_idx[3], ...]
    elif n_dims == 3:
        new_volume = new_volume[crop_idx[0]:crop_idx[3], crop_idx[1]:crop_idx[4], crop_idx[2]:crop_idx[5], ...]
    else:
        sf.system.fatal('cannot crop volumes with more than 3 dimensions')

    if aff is not None:
        aff[0:3, -1] = aff[0:3, -1] + aff[:3, :3] @ crop_idx[:3]
        return new_volume, aff
    else:
        return new_volume


def get_largest_connected_component(mask, structure=None):
    components, n_components = scipy_label(mask, structure)
    return components == np.argmax(np.bincount(components.flat)[1:]) + 1 if n_components > 0 else mask.copy()


def mask_volume(volume, mask=None, threshold=0.1, dilate=0, erode=0, fill_holes=False, masking_value=0,
                return_mask=False, return_copy=True):

    # get info
    new_volume = volume.copy() if return_copy else volume
    vol_shape = list(new_volume.shape)
    n_dims, n_channels = get_dims(vol_shape)

    # get mask and erode/dilate it
    if mask is None:
        mask = new_volume >= threshold
    else:
        assert list(mask.shape[:n_dims]) == vol_shape[:n_dims], 'mask should have shape {0}, or {1}, had {2}'.format(
            vol_shape[:n_dims], vol_shape[:n_dims] + [n_channels], list(mask.shape))
        mask = mask > 0
    if dilate > 0:
        dilate_struct = build_binary_structure(dilate, n_dims)
        mask_to_apply = binary_dilation(mask, dilate_struct)
    else:
        mask_to_apply = mask
    if erode > 0:
        erode_struct = build_binary_structure(erode, n_dims)
        mask_to_apply = binary_erosion(mask_to_apply, erode_struct)
    if fill_holes:
        mask_to_apply = binary_fill_holes(mask_to_apply)

    # replace values outside of mask by padding_char
    if mask_to_apply.shape == new_volume.shape:
        new_volume[np.logical_not(mask_to_apply)] = masking_value
    else:
        new_volume[np.stack([np.logical_not(mask_to_apply)] * n_channels, axis=-1)] = masking_value

    if return_mask:
        return new_volume, mask_to_apply
    else:
        return new_volume


def build_binary_structure(connectivity, n_dims, shape=None):
    if shape is None:
        shape = [connectivity * 2 + 1] * n_dims
    else:
        shape = reformat_to_list(shape, length=n_dims)
    dist = np.ones(shape)
    center = tuple([tuple([int(s / 2)]) for s in shape])
    dist[center] = 0
    dist = distance_transform_edt(dist)
    struct = (dist <= connectivity) * 1
    return struct



def crop_volume(volume, cropping_margin=None, cropping_shape=None, aff=None, return_crop_idx=False, mode='center'):

    assert (cropping_margin is not None) | (cropping_shape is not None), \
        'cropping_margin or cropping_shape should be provided'
    assert not ((cropping_margin is not None) & (cropping_shape is not None)), \
        'only one of cropping_margin or cropping_shape should be provided'

    # get info
    new_volume = volume.copy()
    vol_shape = new_volume.shape
    n_dims, _ = get_dims(vol_shape)

    # find cropping indices
    if cropping_margin is not None:
        cropping_margin = reformat_to_list(cropping_margin, length=n_dims)
        do_cropping = np.array(vol_shape[:n_dims]) > 2 * np.array(cropping_margin)
        min_crop_idx = [cropping_margin[i] if do_cropping[i] else 0 for i in range(n_dims)]
        max_crop_idx = [vol_shape[i] - cropping_margin[i] if do_cropping[i] else vol_shape[i] for i in range(n_dims)]
    else:
        cropping_shape = reformat_to_list(cropping_shape, length=n_dims)
        if mode == 'center':
            min_crop_idx = np.maximum([int((vol_shape[i] - cropping_shape[i]) / 2) for i in range(n_dims)], 0)
            max_crop_idx = np.minimum([min_crop_idx[i] + cropping_shape[i] for i in range(n_dims)],
                                      np.array(vol_shape)[:n_dims])
        elif mode == 'random':
            crop_max_val = np.maximum(np.array([vol_shape[i] - cropping_shape[i] for i in range(n_dims)]), 0)
            min_crop_idx = np.random.randint(0, high=crop_max_val + 1)
            max_crop_idx = np.minimum(min_crop_idx + np.array(cropping_shape), np.array(vol_shape)[:n_dims])
        else:
            raise ValueError('mode should be either "center" or "random", had %s' % mode)
    crop_idx = np.concatenate([np.array(min_crop_idx), np.array(max_crop_idx)])

    # crop volume
    if n_dims == 2:
        new_volume = new_volume[crop_idx[0]: crop_idx[2], crop_idx[1]: crop_idx[3], ...]
    elif n_dims == 3:
        new_volume = new_volume[crop_idx[0]: crop_idx[3], crop_idx[1]: crop_idx[4], crop_idx[2]: crop_idx[5], ...]

    # sort outputs
    output = [new_volume]
    if aff is not None:
        aff[0:3, -1] = aff[0:3, -1] + aff[:3, :3] @ np.array(min_crop_idx)
        output.append(aff)
    if return_crop_idx:
        output.append(crop_idx)
    return output[0] if len(output) == 1 else tuple(output)



def rescale_volume(volume, new_min=0, new_max=255, min_percentile=2., max_percentile=98., use_positive_only=False):

    # select only positive intensities
    new_volume = volume.copy()
    intensities = new_volume[new_volume > 0] if use_positive_only else new_volume.flatten()

    # define min and max intensities in original image for normalisation
    robust_min = np.min(intensities) if min_percentile == 0 else np.percentile(intensities, min_percentile)
    robust_max = np.max(intensities) if max_percentile == 100 else np.percentile(intensities, max_percentile)

    # trim values outside range
    new_volume = np.clip(new_volume, robust_min, robust_max)

    # rescale image
    if robust_min != robust_max:
        return new_min + (new_volume - robust_min) / (robust_max - robust_min) * (new_max - new_min)
    else:  # avoid dividing by zero
        return np.zeros_like(new_volume)




def pad_volume(volume, padding_shape, padding_value=0, aff=None, return_pad_idx=False):
    # get info
    new_volume = volume.copy()
    vol_shape = new_volume.shape
    n_dims, n_channels = get_dims(vol_shape)
    padding_shape = reformat_to_list(padding_shape, length=n_dims, dtype='int')

    # check if need to pad
    if np.any(np.array(padding_shape, dtype='int32') > np.array(vol_shape[:n_dims], dtype='int32')):

        # get padding margins
        min_margins = np.maximum(np.int32(np.floor((np.array(padding_shape) - np.array(vol_shape)[:n_dims]) / 2)), 0)
        max_margins = np.maximum(np.int32(np.ceil((np.array(padding_shape) - np.array(vol_shape)[:n_dims]) / 2)), 0)
        pad_idx = np.concatenate([min_margins, min_margins + np.array(vol_shape[:n_dims])])
        pad_margins = tuple([(min_margins[i], max_margins[i]) for i in range(n_dims)])
        if n_channels > 1:
            pad_margins = tuple(list(pad_margins) + [(0, 0)])

        # pad volume
        new_volume = np.pad(new_volume, pad_margins, mode='constant', constant_values=padding_value)

        if aff is not None:
            if n_dims == 2:
                min_margins = np.append(min_margins, 0)
            aff[:-1, -1] = aff[:-1, -1] - aff[:-1, :-1] @ min_margins

    else:
        pad_idx = np.concatenate([np.array([0] * n_dims), np.array(vol_shape[:n_dims])])

    # sort outputs
    output = [new_volume]
    if aff is not None:
        output.append(aff)
    if return_pad_idx:
        output.append(pad_idx)
    return output[0] if len(output) == 1 else tuple(output)



def add_axis(x, axis=0):
    axis = reformat_to_list(axis)
    for ax in axis:
        x = np.expand_dims(x, axis=ax)
    return x


def volshape_to_meshgrid(volshape, **kwargs):
    """
    compute Tensor meshgrid from a volume size
    """

    isint = [float(d).is_integer() for d in volshape]
    if not all(isint):
        raise ValueError("volshape needs to be a list of integers")

    linvec = [tf.range(0, d) for d in volshape]
    return meshgrid(*linvec, **kwargs)


def meshgrid(*args, **kwargs):

    indexing = kwargs.pop("indexing", "xy")
    if kwargs:
        key = list(kwargs.keys())[0]
        raise TypeError("'{}' is an invalid keyword argument "
                        "for this function".format(key))

    if indexing not in ("xy", "ij"):
        raise ValueError("indexing parameter must be either 'xy' or 'ij'")

    # with ops.name_scope(name, "meshgrid", args) as name:
    ndim = len(args)
    s0 = (1,) * ndim

    # Prepare reshape by inserting dimensions with size 1 where needed
    output = []
    for i, x in enumerate(args):
        output.append(tf.reshape(tf.stack(x), (s0[:i] + (-1,) + s0[i + 1::])))
    # Create parameters for broadcasting each tensor to the full size
    shapes = [tf.size(x) for x in args]
    sz = [x.get_shape().as_list()[0] for x in args]

    # output_dtype = tf.convert_to_tensor(args[0]).dtype.base_dtype
    if indexing == "xy" and ndim > 1:
        output[0] = tf.reshape(output[0], (1, -1) + (1,) * (ndim - 2))
        output[1] = tf.reshape(output[1], (-1, 1) + (1,) * (ndim - 2))
        shapes[0], shapes[1] = shapes[1], shapes[0]
        sz[0], sz[1] = sz[1], sz[0]

    # This is the part of the implementation from tf that is slow.
    # We replace it below to get a ~6x speedup (essentially using tile instead of * tf.ones())
    # mult_fact = tf.ones(shapes, output_dtype)
    # return [x * mult_fact for x in output]
    for i in range(len(output)):
        stack_sz = [*sz[:i], 1, *sz[(i + 1):]]
        if indexing == 'xy' and ndim > 1 and i < 2:
            stack_sz[0], stack_sz[1] = stack_sz[1], stack_sz[0]
        output[i] = tf.tile(output[i], tf.stack(stack_sz))
    return output


def gaussian_kernel(sigma, max_sigma=None, blur_range=None, separable=True):

    # convert sigma into a tensor
    if not tf.is_tensor(sigma):
        sigma_tens = tf.convert_to_tensor(reformat_to_list(sigma), dtype='float32')
    else:
        assert max_sigma is not None, 'max_sigma must be provided when sigma is given as a tensor'
        sigma_tens = sigma
    shape = sigma_tens.get_shape().as_list()

    # get n_dims and batchsize
    if shape[0] is not None:
        n_dims = shape[0]
        batchsize = None
    else:
        n_dims = shape[1]
        batchsize = tf.split(tf.shape(sigma_tens), [1, -1])[0]

    # reformat max_sigma
    if max_sigma is not None:  # dynamic blurring
        max_sigma = np.array(reformat_to_list(max_sigma, length=n_dims))
    else:  # sigma is fixed
        max_sigma = np.array(reformat_to_list(sigma, length=n_dims))

    # randomise the burring std dev and/or split it between dimensions
    if blur_range is not None:
        if blur_range != 1:
            sigma_tens = sigma_tens * tf.random.uniform(tf.shape(sigma_tens), minval=1 / blur_range, maxval=blur_range)

    # get size of blurring kernels
    windowsize = np.int32(np.ceil(2.5 * max_sigma) / 2) * 2 + 1

    if separable:

        split_sigma = tf.split(sigma_tens, [1] * n_dims, axis=-1)

        kernels = list()
        comb = np.array(list(combinations(list(range(n_dims)), n_dims - 1))[::-1])
        for (i, wsize) in enumerate(windowsize):

            if wsize > 1:

                # build meshgrid and replicate it along batch dim if dynamic blurring
                locations = tf.cast(tf.range(0, wsize), 'float32') - (wsize - 1) / 2
                if batchsize is not None:
                    locations = tf.tile(tf.expand_dims(locations, axis=0),
                                        tf.concat([batchsize, tf.ones(tf.shape(tf.shape(locations)), dtype='int32')],
                                                  axis=0))
                    comb[i] += 1

                # compute gaussians
                exp_term = -K.square(locations) / (2 * split_sigma[i] ** 2)
                g = tf.exp(exp_term - tf.math.log(np.sqrt(2 * np.pi) * split_sigma[i]))
                g = g / tf.reduce_sum(g)

                for axis in comb[i]:
                    g = tf.expand_dims(g, axis=axis)
                kernels.append(tf.expand_dims(tf.expand_dims(g, -1), -1))

            else:
                kernels.append(None)

    else:

        # build meshgrid
        mesh = [tf.cast(f, 'float32') for f in volshape_to_meshgrid(windowsize, indexing='ij')]
        diff = tf.stack([mesh[f] - (windowsize[f] - 1) / 2 for f in range(len(windowsize))], axis=-1)

        # replicate meshgrid to batch size and reshape sigma_tens
        if batchsize is not None:
            diff = tf.tile(tf.expand_dims(diff, axis=0),
                           tf.concat([batchsize, tf.ones(tf.shape(tf.shape(diff)), dtype='int32')], axis=0))
            for i in range(n_dims):
                sigma_tens = tf.expand_dims(sigma_tens, axis=1)
        else:
            for i in range(n_dims):
                sigma_tens = tf.expand_dims(sigma_tens, axis=0)

        # compute gaussians
        sigma_is_0 = tf.equal(sigma_tens, 0)
        exp_term = -K.square(diff) / (2 * tf.where(sigma_is_0, tf.ones_like(sigma_tens), sigma_tens)**2)
        norms = exp_term - tf.math.log(tf.where(sigma_is_0, tf.ones_like(sigma_tens), np.sqrt(2 * np.pi) * sigma_tens))
        kernels = K.sum(norms, -1)
        kernels = tf.exp(kernels)
        kernels /= tf.reduce_sum(kernels)
        kernels = tf.expand_dims(tf.expand_dims(kernels, -1), -1)

    return kernels


def get_mapping_lut(source, dest=None):
    """This functions returns the look-up table to map a list of N values (source) to another list (dest).
    If the second list is not given, we assume it is equal to [0, ..., N-1]."""

    # initialise
    source = np.array(reformat_to_list(source), dtype='int32')
    n_labels = source.shape[0]

    # build new label list if neccessary
    if dest is None:
        dest = np.arange(n_labels, dtype='int32')
    else:
        assert len(source) == len(dest), 'label_list and new_label_list should have the same length'
        dest = np.array(reformat_to_list(dest, dtype='int'))

    # build look-up table
    lut = np.zeros(np.max(source) + 1, dtype='int32')
    for source, dest in zip(source, dest):
        lut[source] = dest

    return lut


class GaussianBlur(KL.Layer):
    """Applies gaussian blur to an input image."""

    def __init__(self, sigma, random_blur_range=None, use_mask=False, **kwargs):
        self.sigma = reformat_to_list(sigma)
        assert np.all(np.array(self.sigma) >= 0), 'sigma should be superior or equal to 0'
        self.use_mask = use_mask

        self.n_dims = None
        self.n_channels = None
        self.blur_range = random_blur_range
        self.stride = None
        self.separable = None
        self.kernels = None
        self.convnd = None
        super(GaussianBlur, self).__init__(**kwargs)

    def get_config(self):
        config = super().get_config()
        config["sigma"] = self.sigma
        config["random_blur_range"] = self.blur_range
        config["use_mask"] = self.use_mask
        return config

    def build(self, input_shape):

        # get shapes
        if self.use_mask:
            assert len(input_shape) == 2, 'please provide a mask as second layer input when use_mask=True'
            self.n_dims = len(input_shape[0]) - 2
            self.n_channels = input_shape[0][-1]
        else:
            self.n_dims = len(input_shape) - 2
            self.n_channels = input_shape[-1]

        # prepare blurring kernel
        self.stride = [1]*(self.n_dims+2)
        self.sigma = reformat_to_list(self.sigma, length=self.n_dims)
        self.separable = np.linalg.norm(np.array(self.sigma)) > 5
        if self.blur_range is None:  # fixed kernels
            self.kernels = gaussian_kernel(self.sigma, separable=self.separable)
        else:
            self.kernels = None

        # prepare convolution
        self.convnd = getattr(tf.nn, 'conv%dd' % self.n_dims)

        self.built = True
        super(GaussianBlur, self).build(input_shape)

    def call(self, inputs, **kwargs):

        if self.use_mask:
            image = inputs[0]
            mask = tf.cast(inputs[1], 'bool')
        else:
            image = inputs
            mask = None

        # redefine the kernels at each new step when blur_range is activated
        if self.blur_range is not None:
            self.kernels = gaussian_kernel(self.sigma, blur_range=self.blur_range, separable=self.separable)

        if self.separable:
            for k in self.kernels:
                if k is not None:
                    image = tf.concat([self.convnd(tf.expand_dims(image[..., n], -1), k, self.stride, 'SAME')
                                       for n in range(self.n_channels)], -1)
                    if self.use_mask:
                        maskb = tf.cast(mask, 'float32')
                        maskb = tf.concat([self.convnd(tf.expand_dims(maskb[..., n], -1), k, self.stride, 'SAME')
                                           for n in range(self.n_channels)], -1)
                        image = image / (maskb + keras.backend.epsilon())
                        image = tf.where(mask, image, tf.zeros_like(image))
        else:
            if any(self.sigma):
                image = tf.concat([self.convnd(tf.expand_dims(image[..., n], -1), self.kernels, self.stride, 'SAME')
                                   for n in range(self.n_channels)], -1)
                if self.use_mask:
                    maskb = tf.cast(mask, 'float32')
                    maskb = tf.concat([self.convnd(tf.expand_dims(maskb[..., n], -1), self.kernels, self.stride, 'SAME')
                                       for n in range(self.n_channels)], -1)
                    image = image / (maskb + keras.backend.epsilon())
                    image = tf.where(mask, image, tf.zeros_like(image))

        return image


class ConvertLabels(KL.Layer):

    def __init__(self, source_values, dest_values=None, **kwargs):
        self.source_values = source_values
        self.dest_values = dest_values
        self.lut = None
        super(ConvertLabels, self).__init__(**kwargs)

    def get_config(self):
        config = super().get_config()
        config["source_values"] = self.source_values
        config["dest_values"] = self.dest_values
        return config

    def build(self, input_shape):
        self.lut = tf.convert_to_tensor(get_mapping_lut(self.source_values, dest=self.dest_values), dtype='int32')
        self.built = True
        super(ConvertLabels, self).build(input_shape)

    def call(self, inputs, **kwargs):
        return tf.gather(self.lut, tf.cast(inputs, dtype='int32'))




# execute script
if __name__ == '__main__':
    main()

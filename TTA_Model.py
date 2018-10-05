# Code base on https://github.com/tsterbak/keras_tta/blob/master/keras_tta.py

import numpy as np
import cv2
import os
from keras.models import load_model, Model
from keras.layers import Dense, Activation
from keras.preprocessing.image import ImageDataGenerator, load_img, img_to_array
import re
from keras import backend as K

class TTA_Model():
    """A simple TTA wrapper for keras computer vision models.
    Args:
        model (keras model): A fitted keras model with a predict method.
        n (int): Number of images for each sample within which the average will
                                                                        be done

    """

    def __init__(self, model, n, mean = None, std = None, bf_soft = False,
                    exclude_outliers = 0):
        self.model = model
        self.n = n
        self.mean = mean
        self.std = std
        self.bf_soft = bf_soft
        self.function_bf_soft = None
        self.exclude_outliers = exclude_outliers
        if self.bf_soft:
            self.function_bf_soft = self.get_before_softmax()

    def get_before_softmax(self):
        """Remake the last dense layer to get access to
        activation before softmax be applied"""
        if self.model:
            temp = self.model.layers[-2].output
            temp = Dense(self.model.layers[-1].output.shape[1]._value, name = "new_dense")(temp)
            preds = Activation('softmax', name = "new_activation")(temp)

            new_model = Model(inputs = self.model.input, outputs = preds)
            new_model.layers[-2].set_weights(self.model.layers[-1].get_weights())
            #self.set_model(new_model)

            return K.function([new_model.layers[0].input], [new_model.layers[-2].output])

    def set_exclude_outliers(self, n):
        self.exclude_outliers = n

    def set_model(self, model):
        self.model = model
        self.set_bf_soft()

    def set_bf_soft(self):
        if self.bf_soft:
            self.function_bf_soft = self.get_before_softmax()
            #self.get_before_softmax()

    def set_n(self, n):
        self.n = n

    def set_mean(self, mean):
        self.mean = mean

    def set_std(self, std):
        self.std = std

    def remove_outliers(self, preds):

        if (self.outliers > 0):
            if (len(preds.shape) == 3 and preds.shape[0] == 1):
                preds = preds.reshape((preds.shape[1], preds.shape[2]))

            max_list = [{'value':np.max(pred), 'idx':idx} for idx, pred in enumerate(preds)]

            max_list = sorted(max_list, key = lambda k: k['value'])

            for i in range(self.exclude_outliers):
                if (i % 2 == 0):
                    # delete the top maximum
                    del preds[max_list[i]['idx']]
                else:
                    # delete the bottom maximum
                    del preds[max_list[-(i+1)]['idx']]

        return preds

    def check_label(self, pred, idx):

        return self.class_indices[self.ground_truth[idx]] == np.argmax(pred)

    def predict_on_loaded_files(self):


        final_score = []
        for idx in range(self.num_samples//self.n):
            imgs = []
            for i in range(self.n):
                img = load_img(self.filenames[idx * self.n + i],
                                            target_size = (224,224))
                if not type(self.mean) == type(None):
                    img = (img_to_array(img) - self.mean)/self.std
                else:
                    img = img_to_array(img)/255.0
                imgs.append(img)
            pred = self.predict(np.array(imgs))
            final_score.append(self.check_label(pred, idx))

        return np.mean(final_score)

    def predict(self, X):
        """Wraps the predict method of the provided model.

        Args:
            X (numpy array or directory name): The data to get predictions for
                                or the directory where the data can be found
        """

        pred = []
        if(type(X) == np.ndarray):
            for idx in range(0, len(X), self.n):
                if self.bf_soft:
                    total = self.function_bf_soft([X[idx:idx+self.n]])
                else:
                    total = self.model.predict(X[idx:idx+self.n], batch_size = self.n)

                total = self.exclude_outliers(total)
                pred.append(np.mean(total, axis=0))

            return np.array(pred)

        elif(type(X) == str):

            directory = X
            classes = []
            results = []
            final_score = []
            self.filenames = []
            self.ground_truth = []

            # list the classes
            for subdir in sorted(os.listdir(directory)):
                dirpath = os.path.join(directory, subdir)
                # if it's a folder
                if os.path.isdir(dirpath):
                    # save it as a class name
                    classes.append(subdir)
                    # list the samples for each class
                    for img_file in sorted(os.listdir(dirpath)):
                        if (not os.path.join(dirpath, img_file) in self.filenames):
                            # get the file name without extension
                            f, ext = os.path.splitext(img_file)
                            # verify if it's have a pattern of an augmented image
                            name_pat = re.compile(r'(\w+\.*\w+\.*\w+\[.+\]\w+)(\d+)')
                            res = re.search(name_pat, f)
                            # get the base name without the augmentation number
                            base_name, num = res.groups()
                            self.filenames += [os.path.join(dirpath,
                                base_name + str(i) + ext) for i in range(self.n)]
                            self.ground_truth.append(classes[-1])

            self.num_samples = len(self.filenames)
            self.num_classes = len(classes)
            self.class_indices = dict(zip(classes, range(len(classes))))

            print("Found {} images augmented {} times belonging to {} classes".format(self.num_samples//self.n,
                        self.n, self.num_classes))

            for idx in range(self.num_samples//self.n):
                imgs = []
                for i in range(self.n):
                    img = load_img(self.filenames[idx * self.n + i],
                                                target_size = (224,224))
                    if not type(self.mean) == type(None):
                        img = (img_to_array(img) - self.mean)/self.std
                    else:
                        img = img_to_array(img)/255.0
                    imgs.append(img)
                pred = self.predict(np.array(imgs))
                final_score.append(self.check_label(pred, idx))

            return np.mean(final_score)

        else:
            raise TypeError("Invalid type for variable X: {}\n" +
                    "It should be a numpy.ndarray or string".format(type(X)))




def unit_test_predict():
    from applications_train import get_img_fit_flow
    center = True
    model_file = "/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536816640.1023815.h5"
    dataset = "/home/gcgic/Documents/Hemerson/Datasets/UCF11/UCF11_sampled_from_101_VR_Gaussian_H_RGB_sz_99_sg_33_split1_augmented_4/valid/HorseRiding"
    samples = [
    "v_HorseRiding_g01_c01_sz_99.0_sg_33.0_p_[0.5]_0.png",
    "v_HorseRiding_g01_c01_sz_99.0_sg_33.0_p_[0.5]_1.png",
    "v_HorseRiding_g01_c01_sz_99.0_sg_33.0_p_[0.5]_2.png",
    "v_HorseRiding_g01_c01_sz_99.0_sg_33.0_p_[0.5]_3.png"
    ]
    imgs = []

    if center:
        flow_dir = {'directory': os.path.join(os.path.split(os.path.split(dataset)[0])[0], 'training'), 'target_size': (224, 224),
                'batch_size': 25, 'class_mode': 'categorical'}
        data_aug = {'featurewise_center': True, 'featurewise_std_normalization': True}
        _, stdev, mean = get_img_fit_flow(data_aug, 1, flow_dir)

    for sample in samples:
        # img = cv2.imread(os.path.join(dataset,sample))
        # img = cv2.resize(img, dsize=(224,224))
        # img = np.expand_dims(img, axis=0)
        img = load_img(os.path.join(dataset,sample), target_size = (224,224))
        #print("Img shape: {}".format(img.shape))
        if center:
            img = (img_to_array(img)-mean)/stdev
        else:
            img = img_to_array(img)/255.0
        imgs.append(img)

    model = load_model(model_file)

    tta = TTA_Model(model, 4, mean = mean, std = stdev, bf_soft = True)
    preds_tta = tta.predict(np.array(imgs))

    print("Imgs max {} min {}".format(np.max(imgs), np.min(imgs)))

    print("Predictions using TTA:\n{}".format(preds_tta))

    preds = []
    print("Individual predictions:")
    for img in imgs:
        preds.append(model.predict(np.expand_dims(img, axis=0), batch_size = 1))
        print(preds[-1])

    preds = np.mean(preds, axis=0)
    print("mean of individual predictions: \n{}".format(preds))

    print("SUCCESS! :D") if sum([format(a, '.6f')==format(b, '.6f') for a,b in zip(*preds,*preds_tta)]) == len(*preds) else print("FAILURE :'(")

def db_test_predict():
    from applications_train import get_img_fit_flow
    center = True
    model_file = "/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536810325.2233403.h5"
    dataset = "/home/gcgic/Documents/Hemerson/Datasets/UCF11/UCF11_sampled_from_101_VR_Gaussian_H_RGB_sz_99_sg_33_split1_augmented_1/valid"

    model = load_model(model_file)

    if center:
        flow_dir = {'directory': os.path.join(os.path.split(dataset)[0], 'training'), 'target_size': (224, 224),
                'batch_size': 25, 'class_mode': 'categorical'}
        data_aug = {'featurewise_center': True, 'featurewise_std_normalization': True}
        _, stdev, mean = get_img_fit_flow(data_aug, 1, flow_dir)
        datagen = ImageDataGenerator(featurewise_center = True,
                        featurewise_std_normalization = True)
        datagen.mean = mean
        datagen.std = stdev
        tta = TTA_Model(model, 1, mean = mean, std = stdev)
    else:
        datagen = ImageDataGenerator(rescale=1./255)
        tta = TTA_Model(model, 1)


    preds_tta = tta.predict(dataset)

    print("Accuracy using TTA: {}".format(preds_tta))

    generator = datagen.flow_from_directory(dataset, target_size = (224, 224), color_mode='rgb', batch_size = 16, class_mode = 'categorical', shuffle=False)

    model.compile(optimizer='sgd', loss='categorical_crossentropy', metrics=['accuracy'])

    samples = sum([len(files) for r, d, files in os.walk(dataset)])
    score = model.evaluate_generator(generator, samples // 16 + 1)
    print("Metrics names:       {}".format(model.metrics_names))
    print("Score from evaluate: {}".format(score))

def exp_test_predict():
    from applications_train import get_img_fit_flow
    model_file = {
                    4:{
                        1:{
                            590:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536808724.3273613.h5",
                            591:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536809565.2324452.h5",
                            592:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536810325.2233403.h5",
                        },
                        2:{
                            599:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536816640.1023815.h5",
                            600:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536817387.8452928.h5",
                            601:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536818002.6662943.h5",
                        }
                    },
                    16:{
                        1:{
                            605:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536845998.1049383.h5",
                            606:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536850027.5034957.h5",
                            607:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize64_epochs1000_1536852462.8670783.h5",
                        },
                        2:{
                            608:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536854710.6218734.h5",
                            609:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536857141.6546757.h5",
                            610:"/home/gcgic/Downloads/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1536859596.1946797.h5",
                        }
                    }
                }

    dataset = {4:"/home/gcgic/Documents/Hemerson/Datasets/UCF11/UCF11_sampled_from_101_VR_Gaussian_H_RGB_sz_99_sg_33_split1_augmented_4/valid",
              16:"/home/gcgic/Documents/Hemerson/Datasets/UCF11/UCF11_sampled_from_101_VR_Gaussian_H_RGB_sz_99_sg_33_split1_augmented_16/valid"}

    first = True
    tta = None
    res_tta = []
    normal_res = []
    for windows in model_file.keys():

        print("************\n\nAccuracy for dataset augmented in {} windows\n\n************".format(windows))

        flow_dir = {'directory': os.path.join(os.path.split(dataset[windows])[0], 'training'), 'target_size': (224, 224),
                'batch_size': 25, 'class_mode': 'categorical'}
        data_aug = {'featurewise_center': True, 'featurewise_std_normalization': True}
        _, stdev, mean = get_img_fit_flow(data_aug, 1, flow_dir)
        datagen = ImageDataGenerator(featurewise_center = True,
                        featurewise_std_normalization = True)
        datagen.mean = mean
        datagen.std = stdev

        samples = sum([len(files) for r, d, files in os.walk(dataset[windows])])

        tta_per_model = []
        normal_per_model = []

        for model_num in model_file[windows].keys():
            print("************\n\nModel {}\n\n************".format(model_num))
            tta_per_exp = []
            normal_per_exp = []

            for exp in model_file[windows][model_num].keys():
                print("************\n\nExperiment {}\n\n************".format(exp))
                model = load_model(model_file[windows][model_num][exp])
                if first:
                    tta = TTA_Model(model, windows, mean = mean, std = stdev, bf_soft = True)
                    first = False
                    preds_tta = tta.predict(dataset[windows])
                else:
                    tta.set_model(model)
                    preds_tta = tta.predict_on_loaded_files()


                print("Accuracy using TTA: {}".format(preds_tta))

                generator = datagen.flow_from_directory(dataset[windows], target_size = (224, 224), color_mode='rgb', batch_size = 4, class_mode = 'categorical', shuffle=False)
                model.compile(optimizer='sgd', loss='categorical_crossentropy', metrics=['accuracy'])
                score = model.evaluate_generator(generator, samples // 4)
                print("Metrics names:       {}".format(model.metrics_names))
                print("Score from evaluate: {}".format(score))

                print("Using TTA the prediction increased {:05.4f}%".format(100*(preds_tta-score[1])))

                tta_per_exp.append(preds_tta)
                normal_per_exp.append(score[1])

            tta_per_model.append(tta_per_exp)
            normal_per_model.append(normal_per_exp)
        first = True
        res_tta.append(tta_per_model)
        normal_res.append(normal_per_model)



    diff = np.array(res_tta) - np.array(normal_res)

    print("\n**** All differences: \n{}".format(diff))

    print("\n**** General difference mean per window: \n{}".format(np.mean(diff, axis=(1,2))))
    print("\n**** General diferrence mean per model: \n{}".format(np.mean(diff, axis=(0,2))))
    print("\n**** General diferrence mean per windows and model: \n{}".format(np.mean(diff, axis=(2))))

def exp_test_predict101():
    from applications_train import get_img_fit_flow
    model_file = {
                    4:{
                        # 'resnet50':{
                        #             1:{
                        #                 240:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537929486.7611394.h5",
                        #                 241:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537940432.5365655.h5",
                        #                 242:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537952434.4005418.h5",
                        #             },
                        #             2:{
                        #                 243:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537964296.0066204.h5",
                        #                 244:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537975043.6737926.h5",
                        #                 245:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537982274.0607374.h5",
                        #             },
                        #             3:{
                        #                 246:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537989178.0348685.h5",
                        #                 247:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537994134.8487825.h5",
                        #                 248:"/home/gcgic/Documents/Hemerson/fine_tuning_resnet50_best_lrate0.001_bsize16_epochs1000_1537999081.2091162.h5",
                        #             }
                        # },
                        'inceptionv3':{
                                    1:{
                                        249:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538011975.9522138.h5",
                                        250:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538019503.8924916.h5",
                                        251:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538026600.6237442.h5",
                                    },
                                    2:{
                                        252:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538033663.552778.h5",
                                        253:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538040755.9879205.h5",
                                        254:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538047855.8792114.h5",
                                    },
                                    3:{
                                        255:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538054983.460529.h5",
                                        256:"/home/gcgic/Documents/Hemerson/fine_tuning_inceptionv3_best_lrate0.001_bsize16_epochs1000_1538062023.4726079.h5",
                                    }
                        }
                    }
                }

    dataset = {4:"/home/gcgic/Documents/Hemerson/Datasets/UCF101/UCF101_VR_RGB_H_Gaussian_SZ_99_SG_33_split1_window_4/valid"}

    first = True
    tta = None
    res_tta = []
    normal_res = []
    for windows in model_file.keys():

        print("************\n\nAccuracy for dataset augmented in {} windows\n\n************".format(windows))

        flow_dir = {'directory': os.path.join(os.path.split(dataset[windows])[0], 'training'), 'target_size': (224, 224),
                'batch_size': 25, 'class_mode': 'categorical'}
        data_aug = {'featurewise_center': True, 'featurewise_std_normalization': True}
        _, stdev, mean = 0,1,0#get_img_fit_flow(data_aug, 1, flow_dir)
        datagen = ImageDataGenerator(featurewise_center = True,
                        featurewise_std_normalization = True)
        datagen.mean = mean
        datagen.std = stdev

        samples = sum([len(files) for r, d, files in os.walk(dataset[windows])])

        tta_per_bs_model = []
        normal_per_bs_model = []

        for base_model in model_file[windows].keys():
            print("************\n\nBase Model {}\n\n************".format(base_model))
            tta_per_model_cfg = []
            normal_per_model_cfg = []

            for model_cfg in model_file[windows][base_model].keys():
                print("************\n\nModel Configuration {}\n\n************".format(model_cfg))
                tta_per_exp = []
                normal_per_exp = []

                for exp in model_file[windows][base_model][model_cfg].keys():
                    print("************\n\nExperiment {}\n\n************".format(exp))
                    model = load_model(model_file[windows][base_model][model_cfg][exp])
                    if first:
                        tta = TTA_Model(model, windows, mean = mean, std = stdev, bf_soft = True)
                        first = False
                        preds_tta = tta.predict(dataset[windows])
                    else:
                        tta.set_model(model)
                        preds_tta = tta.predict_on_loaded_files()


                    print("Accuracy using TTA: {}".format(preds_tta))

                    generator = datagen.flow_from_directory(dataset[windows], target_size = (224, 224), color_mode='rgb', batch_size = 4, class_mode = 'categorical', shuffle=False)
                    model.compile(optimizer='sgd', loss='categorical_crossentropy', metrics=['accuracy'])
                    score = model.evaluate_generator(generator, samples // 4)
                    print("Metrics names:       {}".format(model.metrics_names))
                    print("Score from evaluate: {}".format(score))

                    print("Using TTA the prediction increased {:05.4f}%".format(100*(preds_tta-score[1])))

                    tta_per_exp.append(preds_tta)
                    normal_per_exp.append(score[1])
                    K.clear_session()

                tta_per_model_cfg.append(tta_per_exp)
                normal_per_model_cfg.append(normal_per_exp)

            tta_per_bs_model.append(tta_per_model_cfg)
            normal_per_bs_model.append(normal_per_model_cfg)
        first = True
        res_tta.append(tta_per_bs_model)
        normal_res.append(normal_per_bs_model)



    diff = np.array(res_tta) - np.array(normal_res)

    print("\n**** All differences: \n{}".format(diff))

    print("\n**** General difference mean per window: \n{}".format(np.mean(diff, axis=(1,2,3))))
    print("\n**** General diferrence mean per base model: \n{}".format(np.mean(diff, axis=(0,2,3))))
    print("\n**** General diferrence mean per model configuration: \n{}".format(np.mean(diff, axis=(0,1,3))))

    return diff

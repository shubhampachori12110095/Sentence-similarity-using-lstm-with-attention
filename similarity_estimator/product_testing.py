""" Tests the performance of the trained model by checking its predictive accuracy on n randomly sampled items. """

import os
import pickle
import torch
from similarity_estimator.networks import SiameseClassifier
from similarity_estimator.options import TestingOptions, ClusterOptions
from similarity_estimator.sim_util import load_similarity_data
from utils.data_server import DataServer
from utils.init_and_storage import load_network
import json
import re
import jieba
import time


TESTINGNUM = 2059


def cut_sent(sentence):
    """choose word level cut or character level cut"""
    sentence = re.sub('\t', '', sentence)
    # word level
    # sentence = ' '.join(jieba.cut(sentence))

    # character level
    this_list = []
    for word in sentence.strip():
        this_list.append(word)
    sentence = ' '.join(this_list)

    return sentence


def top_n(score_dict, label_dict, class_dict, n=5):
    cnt = 0
    new_dict = sorted(score_dict.items(), key=lambda asd: asd[1], reverse=True)
    for i in range(n):
        for item in class_dict:
            for sentence in class_dict[item]:
                sent = cut_sent(sentence)
                if new_dict[i][0] == sent:
                    record_dict={
                        'class': item,
                        'sentence': new_dict[i][0],
                        'score': new_dict[i][1],
                        'label': label_dict[sent]
                    }
                    print(record_dict)
                    fo.write(json.dumps(record_dict, ensure_ascii=False))
                    fo.write('\n')
                    if 1.0 in label_dict[sent]:
                        cnt = 1
                        return cnt
                else:
                    pass
    return cnt


def test_loop(TESTINGSET='testing_set.txt'):
    # Initialize testing parameters
    opt = TestingOptions()
    # Obtain data
    extended_corpus_path = os.path.join(opt.data_dir, TESTINGSET)
    # corpus_data format: [[('sentence_a', 'sentence_b'),('', '')],['score','']]
    _, corpus_data = load_similarity_data(opt, extended_corpus_path, 'sick_corpus')
    # Load extended vocab
    vocab_path = os.path.join(opt.save_dir, 'extended_vocab.pkl')
    with open(vocab_path, 'rb') as f:
        _, vocab = pickle.load(f)

    # Initialize the similarity classifier
    classifier = SiameseClassifier(vocab.n_words, opt, is_train=False)
    # Load best available configuration (or modify as needed)
    load_network(classifier.encoder_a, 'sim_classifier', 'latest', opt.save_dir)

    # Initialize a data loader from randomly shuffled corpus data; inspection limited to individual items, hence bs=1
    shuffled_loader = DataServer(corpus_data, vocab, opt, is_train=False, use_buckets=False, volatile=True)

    # Keep track of performance
    total_classification_divergence = 0.0
    total_classification_loss = 0.0

    # Test loop
    prediction_dict = {}
    label_dict = {}
    for i, data in enumerate(shuffled_loader):
        # Upon completion
        if i >= TESTINGNUM:
            average_classification_divergence = total_classification_divergence / opt.num_test_samples
            average_classification_loss = total_classification_loss / opt.num_test_samples
            print('=================================================\n'
                  '= Testing concluded after examining %d samples.=\n'
                  '= Average classification divergence is %.4f.  =\n'
                  '= Average classification loss (MSE) is %.4f.  =\n'
                  '=================================================' %
                  (opt.num_test_samples, average_classification_divergence, average_classification_loss))
            break

        s1_var, s2_var, label_var = data
        # Get predictions and update tracking values
        classifier.test_step(s1_var, s2_var, label_var)
        prediction = classifier.prediction
        loss = classifier.loss.data[0]
        divergence = torch.abs((prediction - (label_var - 1.0) / 4.0).data[0])
        total_classification_divergence += divergence
        total_classification_loss += loss

        sentence_a = ' '.join([vocab.index_to_word[int(idx[0])] if idx[0] != 0 else '' for idx in
                               s1_var.data.numpy().tolist()])
        sentence_b = ' '.join([vocab.index_to_word[int(idx[0])] if idx[0] != 0 else '' for idx in
                               s2_var.data.numpy().tolist()])

        sentence_a = sentence_a.strip()
        sentence_b = sentence_b.strip()
        prediction_dict[sentence_b] = prediction.data[0]
        if sentence_b in label_dict:
            label_dict[sentence_b].append((label_var.data[0][0] - 1.0) / 4.0)
        else:
            label_dict[sentence_b] = []
            label_dict[sentence_b].append((label_var.data[0][0] - 1.0) / 4.0)

        temp_dict = {
                    'sentence_b': sentence_b,
                    'prediction': prediction.data[0],
                    'label': (label_var.data[0][0] - 1.0) / 4.0,
                }
        for i in range(len(top_n_dict)):
            if temp_dict['prediction'] > top_n_dict[i]['prediction']:
                temp_dict, top_n_dict[i] = top_n_dict[i], temp_dict
            else:
                continue

    fo.write(sentence_a)
    fo.write('\n')
    print(sentence_a)

    return prediction_dict, label_dict


def test(test_set):
    count = 0
    with open('../data/new_product_title_map.json') as f:
        class_dict = json.load(f)
    prediction_dict, label_dict = test_loop(TESTINGSET=test_set)
    count = top_n(prediction_dict, label_dict, class_dict, 20)
    # top_n_accuracy.append(count)
    return count


def test_1():
    """暴力测试，可用"""
    with open('models/top20_test.txt', 'w') as fo:
        top_n_accuracy = []
        for file_name in range(300):
            test_set = '../data/character_level_data/test_set/' + str(file_name) + '.txt'
            try:
                top_n_accuracy.append(test(test_set))
            except Exception as e:
                print(e)
                pass
            print(file_name)

        print(sum(top_n_accuracy)/len(top_n_accuracy))
        print(sum(top_n_accuracy))
        fo.write(str(sum(top_n_accuracy)) + '\n')
        fo.write(str(sum(top_n_accuracy)/len(top_n_accuracy)) + '\n')


if __name__ == '__main__':
    # test_1()

    start_time = time.time()
    N = 5
    with open('models/top' + str(N) + '_test.txt', 'a+') as fo:
        accuracy_list = []
        top_n_dict = {}
        for file_name in range(300):
            for i in range(N):
                top_n_dict[i] = {
                    'sentence_b': '',
                    'prediction': 0.0,
                    'label': 0.0,
                }
            test_set = '../data/character_level_data/test_set/' + str(file_name) + '.txt'
            try:
                test_loop(test_set)
                bl = 0
                for k in top_n_dict:
                    if top_n_dict[k]['label'] == 1.0:
                        bl = 1.0
                        break
                    else:
                        pass
                accuracy_list.append(bl)
            except Exception as e:
                print(e)
            print(len(accuracy_list))
            fo.write(json.dumps(top_n_dict, ensure_ascii=False))
            fo.write('\n')
            print('Test for %d s.' % (time.time() - start_time))
        print(sum(accuracy_list)/len(accuracy_list))
    end_time = time.time()
    print('Test for %d s.' % (start_time - end_time))

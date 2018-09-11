# QA2D

A model for transforming questions + short answers into full answer sentences. 

The dataset and the models are described in the following paper:

>Demszky, D., Guu, K., & Liang, P. (2018). Transforming Question Answering Datasets Into Natural Language Inference Datasets. arXiv preprint. _arXiv:1809.02922_.[[link](https://arxiv.org/abs/1809.02922)]

This repo contains the code and examples for both the rule-based model and the neural model.

Data available on [Codalab](https://worksheets.codalab.org/worksheets/0xd4ebc52cebb84130a07cbfe81597aaf0/).

### Rule-based model

We illustrate how to use the rule-based model in the designated jupyter notebook. The input sentences have to be dependency parsed. We created our example file in the following manner:
1. Save your tokenized (space-separated) questions and short answers in a file, such as `examples.txt`, where each sentence is a line, one example after the other (i.e. question 1 \<line-break\> short answer 1 \<line-break\> question 2 \<line-break\> short answer 2 \<line-break\> ... question N \<line-break\> short answer N)
2. Convert this file into [CoNLL-U format](http://universaldependencies.org/format.html), `examples.conllu`, with the tags and labels left empty (`_`).
3. POS tag the file. For ours, we used the parser by [Dozat et al. (2017)](https://github.com/tdozat/Parser-v2), which can be used as a tagger as well.
4. Dependency parse the file. We parsed ours with [Dozat et al. (2017)](https://github.com/tdozat/Parser-v2). 
5. Use the resulting, tagged and parsed `examples.conllu` file as an input for the model, as shown in the jupyter notebook `Rule-based Example.ipynb`. 


### Neural model
Coming soon.

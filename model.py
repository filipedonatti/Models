import pandas as pd
import torch
import numpy as np
from tqdm import tqdm
from transformers import BertTokenizerFast
from transformers import BertForTokenClassification
from torch.utils.data import Dataset, DataLoader

import multiprocessing
multiprocessing.set_start_method('fork') 

if __name__ == '__main__':
    multiprocessing.freeze_support()
    
df = pd.read_csv('ner.csv')
labels = [i.split() for i in df['labels'].values.tolist()]

unique_labels = set()
for lb in labels:
    [unique_labels.add(i) for i in lb if i not in unique_labels]
# print(unique_labels)

labels_to_ids = {k: v for v, k in enumerate(sorted(unique_labels))}
ids_to_labels = {v: k for v, k in enumerate(sorted(unique_labels))}
# print(labels_to_ids)


text = df['text'].values.tolist()
example = text[36]
#print(example)

tokenizer = BertTokenizerFast.from_pretrained('bert-base-cased')
text_tokenized = tokenizer(example, padding='max_length', max_length=512, truncation=True, return_tensors='pt')
'''
print(text_tokenized)
print(tokenizer.decode(text_tokenized.input_ids[0]))
'''

def align_label_example(tokenized_input, labels):
    word_ids = tokenized_input.word_ids()
    previous_word_idx = None
    label_ids = []
    for word_idx in word_ids:
        if word_idx is None:
            label_ids.append(-100)
        elif word_idx != previous_word_idx:
            try:
                label_ids.append(labels_to_ids[labels[word_idx]])
            except:
                label_ids.append(-100)
        else:
            label_ids.append(labels_to_ids[labels[word_idx]] if label_all_tokens else -100)
            previous_word_idx = word_idx
    return label_ids;
    
label = labels[36]

label_all_tokens = False
new_label = align_label_example(text_tokenized, label)
'''
print(new_label)
print(tokenizer.convert_ids_to_tokens(text_tokenized['input_ids'][0]))
'''

def align_label(texts, labels):
    tokenized_inputs = tokenizer(texts, padding='max_length', max_length=512, truncation=True)
    word_ids = tokenized_inputs.word_ids()
    
    previous_word_idx = None
    label_ids = []
    for word_idx in word_ids:
        if word_idx is None:
            label_ids.append(-100)
        elif word_idx != previous_word_idx:
            try:
                label_ids.append(labels_to_ids[labels[word_idx]])
            except:
                label_ids.append(-100)
        else:
            try:
                label_ids.append(labels_to_ids[labels[word_idx]] if label_all_tokens else -100)
            except:
                label_ids.append(-100)
        previous_word_idx = word_idx
        
    return label_ids

class DataSequence(torch.utils.data.Dataset):
    def __init__(self, df):
        lb = [i.split() for i in df['labels'].values.tolist()]
        txt = df['text'].values.tolist()
        self.texts = [tokenizer(str(i),
                                padding='max_length', max_length=512, truncation=True, return_tensors='pt') for i in txt]
        self.labels = [align_label(i,j) for i,j in zip(txt, lb)]

def __len__(self):
    return len(self.labels)
def get_batch_labels(self, idx):
    return torch.LongTensor(self.labels[idx])

def __getitem__(self, idx):
    batch_data = self.get_batch_data(idx)
    batch_labels = self.get_batch_labels(idx)
    return batch_data, batch_labels

df = df[0:1000]
df_train, df_val, df_test = np.split(df.sample(frac=1, random_state=42),
    [int(.8 * len(df)), int(.9 * len(df))])


class BertModel(torch.nn.Module):
    def __init__(self):
        super(BertModel, self).__init__()
        self.bert = BertForTokenClassification.from_pretrained('bert-base-cased', num_labels=len(unique_labels))
    def forward(self, input_id, mask, label):
        output = self.bert(input_ids=input_id, attention_mask=mask, labels=label, return_dict=False)
        return output
    
def train_loop(model, df_train, df_val):

    train_dataset = DataSequence(df_train)
    val_dataset = DataSequence(df_val)
    
    train_dataloader = DataLoader(train_dataset, num_workers=4, batch_size=BATCH_SIZE, shuffle=True)
    val_dataloader = DataLoader(val_dataset, num_workers=4, batch_size=BATCH_SIZE)
    
    use_cuda = torch.cuda.is_available()
    device = torch.device('cuda' if use_cuda else 'cpu')
    
    optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE)
    
    if use_cuda:
        model = model.cuda()
        
        best_acc = 0
        best_loss = 1000
        
        for epoch_num in range(EPOCHS):
            total_acc_train = 0
            total_loss_train = 0
            model.train()
        for train_data, train_label in tqdm(train_dataloader):
            train_label = train_label.to(device)
            mask = train_data['attention_mask'].squeeze(1).to(device)
            input_id = train_data['input_ids'].squeeze(1).to(device)
            
            optimizer.zero_grad()
            loss, logits = model(input_id, mask, train_label)
            
            for i in range(logits.shape[0]):
                logits_clean = logits[i][train_label[i] != -100]
                label_clean = train_label[i][train_label[i] != -100]
                predictions = logits_clean.argmax(dim=1)
                acc = (predictions == label_clean).float().mean()
                total_acc_train += acc
                total_loss_train += loss.item()

            loss.backward()
            optimizer.step()

        model.eval()
        total_acc_val = 0
        total_loss_val = 0
        
        for val_data, val_label in val_dataloader:

            val_label = val_label.to(device)
            mask = val_data['attention_mask'].squeeze(1).to(device)
            input_id = val_data['input_ids'].squeeze(1).to(device)

            loss, logits = model(input_id, mask, val_label)

            for i in range(logits.shape[0]):

              logits_clean = logits[i][val_label[i] != -100]
              label_clean = val_label[i][val_label[i] != -100]

              predictions = logits_clean.argmax(dim=1)
              acc = (predictions == label_clean).float().mean()
              total_acc_val += acc
              total_loss_val += loss.item()

        val_accuracy = total_acc_val / len(df_val)
        val_loss = total_loss_val / len(df_val)

        print(
            f'Epochs: {epoch_num + 1} | Loss: {total_loss_train / len(df_train): .3f} | Accuracy: {total_acc_train / len(df_train): .3f} | Val_Loss: {total_loss_val / len(df_val): .3f} | Accuracy: {total_acc_val / len(df_val): .3f}')

LEARNING_RATE = 5e-3
EPOCHS = 5
BATCH_SIZE = 2

model = BertModel()
train_loop(model, df_train, df_val)



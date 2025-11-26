from __future__ import annotations
import torch
from torch.utils.data import DataLoader, TensorDataset
from ..models.lstm_model import LSTMSLIPredictor
from .data_loader import load_sample_sli_slo
from .feature_engineering import add_rolling_features, build_supervised_sequences


def train_lstm(epochs:int=3, lookback:int=24, horizon:int=1, batch_size:int=16, lr:float=1e-3, device:str|None=None):
    device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
    df = load_sample_sli_slo(); df = add_rolling_features(df,'latency_ms',window=12)
    feature_cols=['latency_ms','latency_ms_roll_mean_12','latency_ms_roll_std_12']; target_col='latency_ms'
    X,y = build_supervised_sequences(df,feature_cols,target_col,lookback=lookback,horizon=horizon); y=y[:,0]
    X_t=torch.tensor(X,dtype=torch.float32); y_t=torch.tensor(y,dtype=torch.float32)
    ds=TensorDataset(X_t,y_t); dl=DataLoader(ds,batch_size=batch_size,shuffle=True)
    m=LSTMSLIPredictor(input_size=len(feature_cols)).to(device); opt=torch.optim.Adam(m.parameters(),lr=lr); loss_fn=torch.nn.MSELoss()
    m.train()
    for e in range(epochs):
        tot=0.0
        for xb,yb in dl:
            xb,yb=xb.to(device),yb.to(device)
            opt.zero_grad(); pred=m(xb); loss=loss_fn(pred,yb); loss.backward(); opt.step(); tot+=loss.item()*xb.size(0)
        print(f'[LSTM] epoch {e+1}/{epochs} loss={tot/len(ds):.4f}')
    return m

if __name__=='__main__':
    train_lstm()

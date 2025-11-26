from __future__ import annotations
import torch, torch.nn as nn

class Chomp1d(nn.Module):
    def __init__(self,chomp_size:int):
        super().__init__(); self.chomp_size=chomp_size
    def forward(self,x:torch.Tensor)->torch.Tensor:
        return x[:, :, :-self.chomp_size].contiguous()

class TemporalBlock(nn.Module):
    def __init__(self,in_channels,out_channels,kernel_size,stride,dilation,padding,dropout):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels,out_channels,kernel_size,stride=stride,padding=padding,dilation=dilation)
        self.chomp1 = Chomp1d(padding)
        self.relu1 = nn.ReLU(); self.dropout1 = nn.Dropout(dropout)
        self.conv2 = nn.Conv1d(out_channels,out_channels,kernel_size,stride=stride,padding=padding,dilation=dilation)
        self.chomp2 = Chomp1d(padding)
        self.relu2 = nn.ReLU(); self.dropout2 = nn.Dropout(dropout)
        self.downsample = nn.Conv1d(in_channels,out_channels,1) if in_channels!=out_channels else None
        self.relu = nn.ReLU()
    def forward(self,x:torch.Tensor)->torch.Tensor:
        out = self.conv1(x); out=self.chomp1(out); out=self.relu1(out); out=self.dropout1(out)
        out = self.conv2(out); out=self.chomp2(out); out=self.relu2(out); out=self.dropout2(out)
        res = x if self.downsample is None else self.downsample(x)
        return self.relu(out+res)

class TCN(nn.Module):
    def __init__(self,input_size:int,num_channels:list[int],kernel_size:int=3,dropout:float=0.1):
        super().__init__(); layers=[]
        for i,out_ch in enumerate(num_channels):
            in_ch = input_size if i==0 else num_channels[i-1]
            dilation = 2**i; padding=(kernel_size-1)*dilation
            layers.append(TemporalBlock(in_ch,out_ch,kernel_size,1,dilation,padding,dropout))
        self.network = nn.Sequential(*layers); self.fc = nn.Linear(num_channels[-1],1)
    def forward(self,x:torch.Tensor)->torch.Tensor:
        x = x.transpose(1,2)
        out = self.network(x)
        out = out[:, :, -1]
        return self.fc(out).squeeze(-1)

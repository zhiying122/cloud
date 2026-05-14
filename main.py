import time
from max30102 import MAX30102

try:
    m = MAX30102(channel=4, address=0x57)
    print("MAX30102 初始化成功！")
    
    print("請將手指輕輕放在感測器上...")
    
    while True:
        red, ir = m.read_fifo()
        
        if red is not None:
            if red > 10000:
                print(f"紅光: {red} | 紅外線: {ir}")
            else:
                print("等待手指...", end="\r")
        
        time.sleep(0.05)

except Exception as e:
    print(f"錯誤: {e}")

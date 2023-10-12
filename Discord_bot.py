#!/user/bin/env python
# -*- coding: utf-8 -*-

from requests import get
import logging
import discord
import json
import re
import os
from datetime import datetime
from pprint import pprint

from FinBot import runLoki

try:
    from intent import Loki_Exchange
except:
    from .intent import Loki_Exchange
    
from ArticutAPI import Articut
LOKI_URL = "https://api.droidtown.co/Loki/BulkAPI/"
try:
    accountInfo = json.load(open(os.path.join(os.path.dirname(__file__), "account.info"), encoding="utf-8"))
    USERNAME = accountInfo["username"]
    LOKI_KEY = accountInfo["loki_key"]
except Exception as e:
    print("[ERROR] AccountInfo => {}".format(str(e)))
    USERNAME = ""
    LOKI_KEY = ""
        
articut = Articut(username=accountInfo["username"], apikey=accountInfo["api_key"])
# 意圖過濾器說明
# INTENT_FILTER = []        => 比對全部的意圖 (預設)
# INTENT_FILTER = [intentN] => 僅比對 INTENT_FILTER 內的意圖
INTENT_FILTER = []
INPUT_LIMIT = 20

logging.basicConfig(level=logging.DEBUG)

punctuationPat = re.compile("[,\.\?:;，。？、：；\n]+")
def getLokiResult(inputSTR):
    punctuationPat = re.compile("[,\.\?:;，。？、：；\n]+")
    inputLIST = punctuationPat.sub("\n", inputSTR).split("\n")
    filterLIST = []
    resultDICT = runLoki(inputLIST, filterLIST)
    logging.debug("Loki Result => {}".format(resultDICT))
    return resultDICT

def moneyName(inputSTR): # input src or tgt to get currency  
    moneyDICT = {"歐元": "EUR",
                 "美金": "USD",
                 "日圓": "JPY",
                 "台幣": "TWD",
                 "臺幣": "TWD",
                 "英鎊": "GBP",
                 "法郎": "CHF",
                 "澳幣": "AUD",
                 "港幣": "HKD",
                 "泰銖": "THB"}
    if (inputSTR == None): # init = TWD
        moneyDICT[inputSTR] = "TWD"
    return moneyDICT[inputSTR]

def getTodayExchangeRate(): # get ExchangeRate table
    response = get("https://tw.rter.info/capi.php")
    rateDICT = response.json()
    return rateDICT

def amountSTRconvert(inputSTR): # convert [X元] into [number X]
    resultDICT = {}
    if inputSTR == None: # 沒說換匯金額多少就預設1
        resultDICT["number"] ==1
    else:
        resultDICT = articut.parse(inputSTR, level="lv3") # 有換匯金額就轉成Number
    return resultDICT["number"][inputSTR]

class BotClient(discord.Client):

    def resetMSCwith(self, messageAuthorID):
        '''
        清空與 messageAuthorID 之間的對話記錄
        '''
        templateDICT = {    "id": messageAuthorID,
                             "updatetime" : datetime.now(),
                             "latestQuest": "",
                             "false_count" : 0
        }
        return templateDICT

    async def on_ready(self):
        # ################### Multi-Session Conversation :設定多輪對話資訊 ###################
        self.templateDICT = {"updatetime" : None,
                             "latestQuest": ""
        }
        self.mscDICT = { #userid:templateDICT
        }
        # ####################################################################################
        print('Logged on as {} with id {}'.format(self.user, self.user.id))

    async def on_message(self, message):
        # Don't respond to bot itself. Or it would create a non-stop loop.
        # 如果訊息來自 bot 自己，就不要處理，直接回覆 None。不然會 Bot 會自問自答個不停。
        if message.author == self.user:
            return None

        logging.debug("收到來自 {} 的訊息".format(message.author))
        logging.debug("訊息內容是 {}。".format(message.content))
        if self.user.mentioned_in(message):
            replySTR = "我是預設的回應字串…你會看到我這串字，肯定是出了什麼錯！"
            logging.debug("本 bot 被叫到了！")
            msgSTR = message.content.replace("<@{}> ".format(self.user.id), "").strip()
            logging.debug("人類說：{}".format(msgSTR))
            if msgSTR == "ping":
                replySTR = "pong"
            elif msgSTR == "ping ping":
                replySTR = "pong pong"

# ##########初次對話：這裡是 keyword trigger 的。
            elif msgSTR.lower() in ["哈囉","嗨","你好","您好","hi","hello"]:
                #有講過話(判斷對話時間差)
                if message.author.id in self.mscDICT.keys():
                    timeDIFF = datetime.now() - self.mscDICT[message.author.id]["updatetime"]
                    #有講過話，但與上次差超過 5 分鐘(視為沒有講過話，刷新template)
                    if timeDIFF.total_seconds() >= 300:
                        self.mscDICT[message.author.id] = self.resetMSCwith(message.author.id)
                        replySTR = "嗨嗨，我們好像見過面，但卓騰的隱私政策不允許我記得你的資料，抱歉！"
                    #有講過話，而且還沒超過5分鐘就又跟我 hello (就繼續上次的對話)
                    else:
                        replySTR = self.mscDICT[message.author.id]["latestQuest"]
                #沒有講過話(給他一個新的template)
                else:
                    self.mscDICT[message.author.id] = self.resetMSCwith(message.author.id)
                    replySTR = '''你好👋我叫匯霸🤖，這裡提供美金、日圓、英鎊、法郎、澳幣、港幣、泰銖的換匯台幣計算，
                    如果你需要台幣換港幣，請輸入： 200台幣換港幣'''
                    await message.reply(replySTR)
                    replySTR = msgSTR.title()

# ##########非初次對話：這裡用 Loki 計算語意
            else: #開始處理正式對話
                #從這裡開始接上 NLU 模型
                resultDICT = getLokiResult(msgSTR)
                logging.debug("######\nLoki 處理結果如下：")
                logging.debug(resultDICT)
                         
                src = moneyName(resultDICT["source"][-1]) 
                tgt = moneyName(resultDICT["target"][-1])
                amt = amountSTRconvert(resultDICT['amount'][-1])
                
                rateDICT = getTodayExchangeRate() # get ExchangeRate table
                
                # calculate ExchangeRate by [source -> USD -> target]
                exRate = (1/rateDICT["USD{}".format(src)]["Exrate"]) * (rateDICT["USD{}".format(tgt)]["Exrate"])
                
                #print("兌換為", amt*exRate,tgt) # 金額*匯率                
                replySTR = round(amt*exRate,2) 
                await message.reply("折合{}＄{}元".format(resultDICT["target"][-1],replySTR))


if __name__ == "__main__":
    with open("account.info", encoding="utf-8") as f: #讀取account.info
        accountDICT = json.loads(f.read())
    client = BotClient(intents=discord.Intents.default())
    client.run(accountDICT["discord_token"])

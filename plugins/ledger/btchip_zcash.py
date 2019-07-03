from binascii import hexlify, unhexlify
from struct import pack, unpack

from btchip.btchip import btchip
from btchip.bitcoinTransaction import bitcoinInput, bitcoinOutput
from btchip.bitcoinVarint import readVarint, writeVarint
from btchip.btchipHelpers import parse_bip32_path, writeUint32BE

from electrum_zclassic.transaction import (OVERWINTERED_VERSION_GROUP_ID,
                                        SAPLING_VERSION_GROUP_ID)


class zcashTransaction:

    def __init__(self, data=None):
        self.version = ''
        self.version_group_id = ''
        self.inputs = []
        self.outputs = []
        self.lockTime = ''
        self.expiry_height = ''
        self.value_balance = ''
        self.overwintered = False
        self.n_version = 0
        if data is not None:
            offset = 0
            self.version = data[offset:offset + 4]
            offset += 4
            header = unpack('<I', self.version)[0]
            if header & 0x80000000:
                self.n_version = header & 0x7FFFFFFF
                self.version_group_id = data[offset:offset + 4]
                offset += 4
                version_group_id = unpack('<I', self.version_group_id)[0]
                if (self.n_version == 3
                        and version_group_id == OVERWINTERED_VERSION_GROUP_ID):
                    self.overwintered = True
                elif (self.n_version == 4
                          and version_group_id == SAPLING_VERSION_GROUP_ID):
                    self.overwintered = True
                else:
                    offset -= 4
                    self.version_group_id = ''
                    self.n_version = header
            inputSize = readVarint(data, offset)
            offset += inputSize['size']
            numInputs = inputSize['value']
            for i in range(numInputs):
                tmp = { 'buffer': data, 'offset' : offset}
                self.inputs.append(bitcoinInput(tmp))
                offset = tmp['offset']
            outputSize = readVarint(data, offset)
            offset += outputSize['size']
            numOutputs = outputSize['value']
            for i in range(numOutputs):
                tmp = { 'buffer': data, 'offset' : offset}
                self.outputs.append(bitcoinOutput(tmp))
                offset = tmp['offset']
            self.lockTime = data[offset:offset + 4]
            if self.overwintered:
                offset += 4
                self.expiry_height = data[offset:offset + 4]
                if self.n_version >= 4:
                    offset += 4
                    self.value_balance = data[offset:offset + 8]

    def serializeOutputs(self):
        result = []
        writeVarint(len(self.outputs), result)
        for troutput in self.outputs:
            result.extend(troutput.serialize())
        return result


class btchip_zcash(btchip):

    def startUntrustedTransaction(self, newTransaction, inputIndex, outputList,
                                  redeemScript, version=0x02,
                                  overwintered=False):
        # Start building a fake transaction with the passed inputs
        if newTransaction:
            if overwintered:
                p2 = 0x05 if version == 4 else 0x04
            else:
                p2 = 0x00
        else:
            p2 = 0x80
        apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_START, 0x00, p2 ]
        if overwintered and version == 3:
            params = bytearray([version, 0x00, 0x00, 0x80, 0x70, 0x82, 0xc4, 0x03])
        elif overwintered and version == 4:
            params = bytearray([version, 0x00, 0x00, 0x80, 0x85, 0x20, 0x2f, 0x89])
        else:
            params = bytearray([version, 0x00, 0x00, 0x00])
        writeVarint(len(outputList), params)
        apdu.append(len(params))
        apdu.extend(params)
        self.dongle.exchange(bytearray(apdu))
        # Loop for each input
        currentIndex = 0
        for passedOutput in outputList:
            if ('sequence' in passedOutput) and passedOutput['sequence']:
                sequence = bytearray(unhexlify(passedOutput['sequence']))
            else:
                sequence = bytearray([0xFF, 0xFF, 0xFF, 0xFF]) # default sequence
            apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_START, 0x80, 0x00 ]
            params = []
            script = bytearray(redeemScript)
            if overwintered:
                params.append(0x02)
            elif ('trustedInput' in passedOutput) and passedOutput['trustedInput']:
                params.append(0x01)
            else:
                params.append(0x00)
            if ('trustedInput' in passedOutput) and passedOutput['trustedInput']:
                params.append(len(passedOutput['value']))
            params.extend(passedOutput['value'])
            if currentIndex != inputIndex:
                script = bytearray()
            writeVarint(len(script), params)
            if len(script) == 0:
                params.extend(sequence)
            apdu.append(len(params))
            apdu.extend(params)
            self.dongle.exchange(bytearray(apdu))
            offset = 0
            while(offset < len(script)):
                blockLength = 255
                if ((offset + blockLength) < len(script)):
                    dataLength = blockLength
                else:
                    dataLength = len(script) - offset
                params = script[offset : offset + dataLength]
                if ((offset + dataLength) == len(script)):
                    params.extend(sequence)
                apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_START, 0x80, 0x00, len(params) ]
                apdu.extend(params)
                self.dongle.exchange(bytearray(apdu))
                offset += blockLength
            currentIndex += 1

    def finalizeInput(self, outputAddress, amount, fees, changePath, rawTx=None):
        alternateEncoding = False
        donglePath = parse_bip32_path(changePath)
        if self.needKeyCache:
            self.resolvePublicKeysInPath(changePath)
        result = {}
        outputs = None
        if rawTx is not None:
            try:
                fullTx = zcashTransaction(bytearray(rawTx))
                outputs = fullTx.serializeOutputs()
                if len(donglePath) != 0:
                    apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_FINALIZE_FULL, 0xFF, 0x00 ]
                    params = []
                    params.extend(donglePath)
                    apdu.append(len(params))
                    apdu.extend(params)
                    response = self.dongle.exchange(bytearray(apdu))
                offset = 0
                while (offset < len(outputs)):
                    blockLength = self.scriptBlockLength
                    if ((offset + blockLength) < len(outputs)):
                        dataLength = blockLength
                        p1 = 0x00
                    else:
                        dataLength = len(outputs) - offset
                        p1 = 0x80
                    apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_FINALIZE_FULL, \
                        p1, 0x00, dataLength ]
                    apdu.extend(outputs[offset : offset + dataLength])
                    response = self.dongle.exchange(bytearray(apdu))
                    offset += dataLength
                alternateEncoding = True
            except:
                pass
        if not alternateEncoding:
            apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_FINALIZE, 0x02, 0x00 ]
            params = []
            params.append(len(outputAddress))
            params.extend(bytearray(outputAddress))
            writeHexAmountBE(btc_to_satoshi(str(amount)), params)
            writeHexAmountBE(btc_to_satoshi(str(fees)), params)
            params.extend(donglePath)
            apdu.append(len(params))
            apdu.extend(params)
            response = self.dongle.exchange(bytearray(apdu))
        result['confirmationNeeded'] = response[1 + response[0]] != 0x00
        result['confirmationType'] = response[1 + response[0]]
        if result['confirmationType'] == 0x02:
            result['keycardData'] = response[1 + response[0] + 1:]
        if result['confirmationType'] == 0x03:
            offset = 1 + response[0] + 1
            keycardDataLength = response[offset]
            offset = offset + 1
            result['keycardData'] = response[offset : offset + keycardDataLength]
            offset = offset + keycardDataLength
            result['secureScreenData'] = response[offset:]
        if result['confirmationType'] == 0x04:
            offset = 1 + response[0] + 1
            keycardDataLength = response[offset]
            result['keycardData'] = response[offset + 1 : offset + 1 + keycardDataLength]
        if outputs == None:
            result['outputData'] = response[1 : 1 + response[0]]
        else:
            result['outputData'] = outputs
        return result

    def finalizeInputFull(self, outputData):
        result = {}
        offset = 0
        encryptedOutputData = b""
        while (offset < len(outputData)):
            blockLength = self.scriptBlockLength
            if ((offset + blockLength) < len(outputData)):
                dataLength = blockLength
                p1 = 0x00
            else:
                dataLength = len(outputData) - offset
                p1 = 0x80
            apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_INPUT_FINALIZE_FULL, \
            p1, 0x00, dataLength ]
            apdu.extend(outputData[offset : offset + dataLength])
            response = self.dongle.exchange(bytearray(apdu))
            encryptedOutputData = encryptedOutputData + response[1 : 1 + response[0]]
            offset += dataLength
        if len(response) > 1:
            result['confirmationNeeded'] = response[1 + response[0]] != 0x00
            result['confirmationType'] = response[1 + response[0]]
        if result['confirmationType'] == 0x02:
            result['keycardData'] = response[1 + response[0] + 1:] # legacy
        if result['confirmationType'] == 0x03:
            offset = 1 + response[0] + 1
            keycardDataLength = response[offset]
            offset = offset + 1
            result['keycardData'] = response[offset : offset + keycardDataLength]
            offset = offset + keycardDataLength
            result['secureScreenData'] = response[offset:]
            result['encryptedOutputData'] = encryptedOutputData
        if result['confirmationType'] == 0x04:
            offset = 1 + response[0] + 1
            keycardDataLength = response[offset]
            result['keycardData'] = response[offset + 1 : offset + 1 + keycardDataLength]
        return result

    def untrustedHashSign(self, path, pin="", lockTime=0, sighashType=0x01,
                          version=0x02, overwintered=False):
        if isinstance(pin, str):
            pin = pin.encode('utf-8')
        donglePath = parse_bip32_path(path)
        if self.needKeyCache:
            self.resolvePublicKeysInPath(path)
        apdu = [ self.BTCHIP_CLA, self.BTCHIP_INS_HASH_SIGN, 0x00, 0x00 ]
        params = []
        params.extend(donglePath)
        params.append(len(pin))
        params.extend(bytearray(pin))
        writeUint32BE(lockTime, params)
        params.append(sighashType)
        if overwintered:
            params.extend(bytearray([0]*4))
        apdu.append(len(params))
        apdu.extend(params)
        result = self.dongle.exchange(bytearray(apdu))
        if not result:
            return
        result[0] = 0x30
        return result

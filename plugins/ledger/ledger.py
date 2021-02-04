from struct import pack, unpack
import hashlib
import sys
import traceback

from electrum_zclassic import bitcoin
from electrum_zclassic import constants
from electrum_zclassic.bitcoin import (TYPE_ADDRESS, int_to_hex, var_int,
                                   b58_address_to_hash160,
                                   hash160_to_b58_address)
from electrum_zclassic.i18n import _
from electrum_zclassic.plugins import BasePlugin
from electrum_zclassic.keystore import Hardware_KeyStore
from electrum_zclassic.transaction import Transaction
from ..hw_wallet import HW_PluginBase
from electrum_zclassic.util import print_error, is_verbose, bfh, bh2u, versiontuple


def setAlternateCoinVersions(self, regular, p2sh):
    apdu = [ 0xE0, 0x14, 0x01, 0x05, 0x16, 0x1C, 0xB8, 0x1C, 0xBD, 0x01, 0x08]
    apdu.extend("ZClassic".encode())
    apdu.append(0x03)
    apdu.extend("ZCL".encode())
    self.dongle.exchange(bytearray(apdu))

try:
    import hid
    from btchip.btchipComm import HIDDongleHIDAPI, DongleWait
    from btchip.btchip import btchip
    from btchip.btchipUtils import compress_public_key,format_transaction, get_regular_input_script, get_p2sh_input_script
    from btchip.btchipFirmwareWizard import checkFirmware, updateFirmware
    from btchip.btchipException import BTChipException
    from .btchip_zcash import btchip_zcash, zcashTransaction
    btchip.setAlternateCoinVersions = setAlternateCoinVersions
    BTCHIP = True
    BTCHIP_DEBUG = is_verbose
except ImportError as e:
    BTCHIP = False

MSG_NEEDS_FW_UPDATE_GENERIC = _('Firmware version too old. Please update at') + \
                      ' https://www.ledgerwallet.com'
MSG_NEEDS_FW_UPDATE_OVERWINTER = (_('Firmware version too old for '
                                    'Overwinter/Sapling support. '
                                    'Please update at') +
                                  ' https://www.ledgerwallet.com')
MULTI_OUTPUT_SUPPORT = '1.1.4'
ALTERNATIVE_COIN_VERSION = '1.0.1'
OVERWINTER_SUPPORT = '1.3.3'


def test_pin_unlocked(func):
    """Function decorator to test the Ledger for being unlocked, and if not,
    raise a human-readable exception.
    """

    def catch_exception(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except BTChipException as e:
            if e.sw == 0x6982:
                raise Exception(_('Your Ledger is locked. Please unlock it.'))
            else:
                raise

    return catch_exception

class Ledger_Client():
    def __init__(self, hidDevice):
        self.dongleObject = btchip_zcash(hidDevice)
        self.preflightDone = False

    def is_pairable(self):
        return True

    def close(self):
        self.dongleObject.dongle.close()

    def timeout(self, cutoff):
        pass

    def is_initialized(self):
        return True

    def label(self):
        return ""

    def i4b(self, x):
        return pack('>I', x)

    @test_pin_unlocked
    def has_usable_connection_with_device(self):
        try:
            self.dongleObject.getFirmwareVersion()
        except BaseException as e:
            if e.sw == 0x6d00 or e.sw == 0x6700:
                raise Exception(_("Device is not in ZClassic mode")) from e
            if e.sw == 0x6982:
                raise  # pin lock. decorator will catch it
            if e.sw == 0x6faa:
                raise Exception("Dongle is temporarily locked - please unplug it and replug it again")
            raise e
        return True

    @test_pin_unlocked
    def get_xpub(self, bip32_path, xtype):
        self.checkDevice()
        # bip32_path is of the form 44'/133'/1'
        # S-L-O-W - we don't handle the fingerprint directly, so compute
        # it manually from the previous node
        # This only happens once so it's bearable
        #self.get_client() # prompt for the PIN before displaying the dialog if necessary
        #self.handler.show_message("Computing master public key")
        splitPath = bip32_path.split('/')
        if splitPath[0] == 'm':
            splitPath = splitPath[1:]
            bip32_path = bip32_path[2:]
        fingerprint = 0
        if len(splitPath) > 1:
            prevPath = "/".join(splitPath[0:len(splitPath) - 1])
            nodeData = self.dongleObject.getWalletPublicKey(prevPath)
            publicKey = compress_public_key(nodeData['publicKey'])
            h = hashlib.new('ripemd160')
            h.update(hashlib.sha256(publicKey).digest())
            fingerprint = unpack(">I", h.digest()[0:4])[0]
        nodeData = self.dongleObject.getWalletPublicKey(bip32_path)
        publicKey = compress_public_key(nodeData['publicKey'])
        depth = len(splitPath)
        lastChild = splitPath[len(splitPath) - 1].split('\'')
        childnum = int(lastChild[0]) if len(lastChild) == 1 else 0x80000000 | int(lastChild[0])
        xpub = bitcoin.serialize_xpub(xtype, nodeData['chainCode'], publicKey, depth, self.i4b(fingerprint), self.i4b(childnum))
        return xpub

    def has_detached_pin_support(self, client):
        try:
            client.getVerifyPinRemainingAttempts()
            return True
        except BTChipException as e:
            if e.sw == 0x6d00:
                return False
            raise e

    def is_pin_validated(self, client):
        try:
            # Invalid SET OPERATION MODE to verify the PIN status
            client.dongle.exchange(bytearray([0xe0, 0x26, 0x00, 0x00, 0x01, 0xAB]))
        except BTChipException as e:
            if (e.sw == 0x6982):
                return False
            if (e.sw == 0x6A80):
                return True
            raise e

    def supports_multi_output(self):
        return self.multiOutputSupported

    def supports_overwinter(self):
        return self.overwinterSupported

    def perform_hw1_preflight(self):
        try:
            firmwareInfo = self.dongleObject.getFirmwareVersion()
            firmware = firmwareInfo['version']
            self.multiOutputSupported = versiontuple(firmware) >= versiontuple(MULTI_OUTPUT_SUPPORT)
            self.overwinterSupported = versiontuple(firmware) >= versiontuple(OVERWINTER_SUPPORT)
            self.canAlternateCoinVersions = (versiontuple(firmware) >= versiontuple(ALTERNATIVE_COIN_VERSION)
                                             and firmwareInfo['specialVersion'] >= 0x20)

            if not checkFirmware(firmwareInfo):
                self.dongleObject.dongle.close()
                raise Exception(MSG_NEEDS_FW_UPDATE_GENERIC)
            try:
                self.dongleObject.getOperationMode()
            except BTChipException as e:
                if (e.sw == 0x6985):
                    self.dongleObject.dongle.close()
                    self.handler.get_setup( )
                    # Acquire the new client on the next run
                else:
                    raise e
            if self.has_detached_pin_support(self.dongleObject) and not self.is_pin_validated(self.dongleObject) and (self.handler is not None):
                remaining_attempts = self.dongleObject.getVerifyPinRemainingAttempts()
                if remaining_attempts != 1:
                    msg = "Enter your Ledger PIN - remaining attempts : " + str(remaining_attempts)
                else:
                    msg = "Enter your Ledger PIN - WARNING : LAST ATTEMPT. If the PIN is not correct, the dongle will be wiped."
                confirmed, p, pin = self.password_dialog(msg)
                if not confirmed:
                    raise Exception('Aborted by user - please unplug the dongle and plug it again before retrying')
                pin = pin.encode()
                self.dongleObject.verifyPin(pin)
                if self.canAlternateCoinVersions:
                    self.dongleObject.setAlternateCoinVersions(constants.net.ADDRTYPE_P2PKH,
                                                               constants.net.ADDRTYPE_P2SH)
        except BTChipException as e:
            if (e.sw == 0x6faa):
                raise Exception("Dongle is temporarily locked - please unplug it and replug it again")
            if ((e.sw & 0xFFF0) == 0x63c0):
                raise Exception("Invalid PIN - please unplug the dongle and plug it again before retrying")
            if e.sw == 0x6f00 and e.message == 'Invalid channel':
                # based on docs 0x6f00 might be a more general error, hence we also compare message to be sure
                raise Exception("Invalid channel.\n"
                                "Please make sure that 'Browser support' is disabled on your device.")
            raise e

    def checkDevice(self):
        if not self.preflightDone:
            try:
                self.perform_hw1_preflight()
            except BTChipException as e:
                if e.sw == 0x6d00 or e.sw == 0x6700:
                    raise Exception(_("Device is not in ZClassic mode")) from e
                raise e
            self.preflightDone = True

    def password_dialog(self, msg=None):
        response = self.handler.get_word(msg)
        if response is None:
            return False, None, None
        return True, response, response


class Ledger_KeyStore(Hardware_KeyStore):
    hw_type = 'ledger'
    device = 'Ledger'

    def __init__(self, d):
        Hardware_KeyStore.__init__(self, d)
        # Errors and other user interaction is done through the wallet's
        # handler.  The handler is per-window and preserved across
        # device reconnects
        self.force_watching_only = False
        self.signing = False
        self.cfg = d.get('cfg', {'mode':0,'pair':''})

    def dump(self):
        obj = Hardware_KeyStore.dump(self)
        obj['cfg'] = self.cfg
        return obj

    def get_derivation(self):
        return self.derivation

    def get_client(self):
        return self.plugin.get_client(self).dongleObject

    def get_client_electrum(self):
        return self.plugin.get_client(self)

    def give_error(self, message, clear_client = False):
        print_error(message)
        if not self.signing:
            self.handler.show_error(message)
        else:
            self.signing = False
        if clear_client:
            self.client = None
        raise Exception(message)

    def set_and_unset_signing(func):
        """Function decorator to set and unset self.signing."""
        def wrapper(self, *args, **kwargs):
            try:
                self.signing = True
                return func(self, *args, **kwargs)
            finally:
                self.signing = False
        return wrapper

    def address_id_stripped(self, address):
        # Strip the leading "m/"
        change, index = self.get_address_index(address)
        derivation = self.derivation
        address_path = "%s/%d/%d"%(derivation, change, index)
        return address_path[2:]

    def decrypt_message(self, pubkey, message, password):
        raise RuntimeError(_('Encryption and decryption are currently not supported for {}').format(self.device))

    @test_pin_unlocked
    @set_and_unset_signing
    def sign_message(self, sequence, message, password):
        message = message.encode('utf8')
        message_hash = hashlib.sha256(message).hexdigest().upper()
        # prompt for the PIN before displaying the dialog if necessary
        client = self.get_client()
        address_path = self.get_derivation()[2:] + "/%d/%d"%sequence
        self.handler.show_message("Signing message ...\r\nMessage hash: "+message_hash)
        try:
            info = client.signMessagePrepare(address_path, message)
            pin = ""
            if info['confirmationNeeded']:
                pin = self.handler.get_auth(info) # does the authenticate dialog and returns pin
                if not pin:
                    raise UserWarning(_('Cancelled by user'))
                pin = str(pin).encode()
            signature = client.signMessageSign(pin)
        except BTChipException as e:
            if e.sw == 0x6a80:
                self.give_error("Unfortunately, this message cannot be signed by the Ledger wallet. Only alphanumerical messages shorter than 140 characters are supported. Please remove any extra characters (tab, carriage return) and retry.")
            elif e.sw == 0x6985:  # cancelled by user
                return b''
            elif e.sw == 0x6982:
                raise  # pin lock. decorator will catch it
            else:
                self.give_error(e, True)
        except UserWarning:
            self.handler.show_error(_('Cancelled by user'))
            return b''
        except Exception as e:
            self.give_error(e, True)
        finally:
            self.handler.finished()
        # Parse the ASN.1 signature
        rLength = signature[3]
        r = signature[4 : 4 + rLength]
        sLength = signature[4 + rLength + 1]
        s = signature[4 + rLength + 2:]
        if rLength == 33:
            r = r[1:]
        if sLength == 33:
            s = s[1:]
        # And convert it
        return bytes([27 + 4 + (signature[0] & 0x01)]) + r + s

    @test_pin_unlocked
    @set_and_unset_signing
    def sign_transaction(self, tx, password):
        if tx.is_complete():
            return

        inputs = []
        inputsPaths = []
        pubKeys = []
        chipInputs = []
        redeemScripts = []
        signatures = []
        changePath = ""
        changeAmount = None
        output = None
        outputAmount = None
        p2shTransaction = False
        pin = ""
        client = self.get_client()   # prompt for the PIN before displaying the dialog if necessary
        client_electrum = self.get_client_electrum()

        # Fetch inputs of the transaction to sign
        derivations = self.get_tx_derivations(tx)
        for txin in tx.inputs():
            if txin['type'] == 'coinbase':
                self.give_error("Coinbase not supported")     # should never happen

            if txin['type'] in ['p2sh']:
                p2shTransaction = True

            pubkeys, x_pubkeys = tx.get_sorted_pubkeys(txin)
            for i, x_pubkey in enumerate(x_pubkeys):
                if x_pubkey in derivations:
                    signingPos = i
                    s = derivations.get(x_pubkey)
                    hwAddress = "%s/%d/%d" % (self.get_derivation()[2:], s[0], s[1])
                    break
            else:
                self.give_error("No matching x_key for sign_transaction") # should never happen

            redeemScript = Transaction.get_preimage_script(txin)
            if txin.get('prev_tx') is None:  # and not Transaction.is_segwit_input(txin):
                # note: offline signing does not work atm even with segwit inputs for ledger
                raise Exception(_('Offline signing with {} is not supported.').format(self.device))
            inputs.append([txin['prev_tx'].raw, txin['prevout_n'], redeemScript, txin['prevout_hash'], signingPos, txin.get('sequence', 0xffffffff - 1) ])
            inputsPaths.append(hwAddress)
            pubKeys.append(pubkeys)

        # Sanity check
        if p2shTransaction:
            for txin in tx.inputs():
                if txin['type'] != 'p2sh':
                    self.give_error("P2SH / regular input mixed in same transaction not supported") # should never happen

        txOutput = var_int(len(tx.outputs()))
        for txout in tx.outputs():
            output_type, addr, amount = txout
            txOutput += int_to_hex(amount, 8)
            script = tx.pay_script(output_type, addr)
            txOutput += var_int(len(script)//2)
            txOutput += script
        txOutput = bfh(txOutput)

        # Recognize outputs - only one output and one change is authorized
        if not p2shTransaction:
            if not client_electrum.supports_multi_output():
                if len(tx.outputs()) > 2:
                    self.give_error("Transaction with more than 2 outputs not supported")
            for _type, address, amount in tx.outputs():
                assert _type == TYPE_ADDRESS
                info = tx.output_info.get(address)
                if (info is not None) and len(tx.outputs()) > 1 \
                        and info[0][0] == 1:  # "is on 'change' branch"
                    index, xpubs, m = info
                    changePath = self.get_derivation()[2:] + "/%d/%d"%index
                    changeAmount = amount
                else:
                    output = address
                    if not client_electrum.canAlternateCoinVersions:
                        v, h = b58_address_to_hash160(address)
                        if v == constants.net.ADDRTYPE_P2PKH:
                            output = hash160_to_b58_address(h, 0)
                    outputAmount = amount

        self.handler.show_message(_("Confirm Transaction on your Ledger device..."))
        try:
            # Get trusted inputs from the original transactions
            for utxo in inputs:
                sequence = int_to_hex(utxo[5], 4)
                if tx.overwintered:
                    txtmp = zcashTransaction(bfh(utxo[0]))
                    tmp = bfh(utxo[3])[::-1]
                    tmp += bfh(int_to_hex(utxo[1], 4))
                    tmp += txtmp.outputs[utxo[1]].amount
                    chipInputs.append({'value' : tmp, 'sequence' : sequence})
                    redeemScripts.append(bfh(utxo[2]))
                elif not p2shTransaction:
                    txtmp = zcashTransaction(bfh(utxo[0]))
                    trustedInput = client.getTrustedInput(txtmp, utxo[1])
                    trustedInput['sequence'] = sequence
                    chipInputs.append(trustedInput)
                    redeemScripts.append(txtmp.outputs[utxo[1]].script)
                else:
                    tmp = bfh(utxo[3])[::-1]
                    tmp += bfh(int_to_hex(utxo[1], 4))
                    chipInputs.append({'value' : tmp, 'sequence' : sequence})
                    redeemScripts.append(bfh(utxo[2]))
            # Sign all inputs
            firstTransaction = True
            inputIndex = 0
            rawTx = tx.serialize()
            client.enableAlternate2fa(False)
            if tx.overwintered:
                client.startUntrustedTransaction(True, inputIndex, chipInputs,
                                                            redeemScripts[inputIndex],
                                                            version=tx.version,
                                                            overwintered=tx.overwintered)
                if changePath:
                    # we don't set meaningful outputAddress, amount and fees
                    # as we only care about the alternateEncoding==True branch
                    outputData = client.finalizeInput(b'', 0, 0, changePath, bfh(rawTx))
                else:
                    outputData = client.finalizeInputFull(txOutput)

                if tx.overwintered:
                    inputSignature = client.untrustedHashSign('',
                                                                         '', lockTime=tx.locktime,
                                                                         version=tx.version,
                                                                         overwintered=tx.overwintered)
                outputData['outputData'] = txOutput
                transactionOutput = outputData['outputData']
                if outputData['confirmationNeeded']:
                    outputData['address'] = output
                    self.handler.finished()
                    pin = self.handler.get_auth( outputData ) # does the authenticate dialog and returns pin
                    if not pin:
                        raise UserWarning()
                    if pin != 'paired':
                        self.handler.show_message(_("Confirmed. Signing Transaction..."))
                while inputIndex < len(inputs):
                    singleInput = [ chipInputs[inputIndex] ]
                    client.startUntrustedTransaction(False, 0, singleInput,
                                                                redeemScripts[inputIndex],
                                                                version=tx.version,
                                                                overwintered=tx.overwintered)
                    inputSignature = client.untrustedHashSign(inputsPaths[inputIndex],
                                                                         pin, lockTime=tx.locktime,
                                                                         version=tx.version,
                                                                         overwintered=tx.overwintered)
                    inputSignature[0] = 0x30 # force for 1.4.9+
                    signatures.append(inputSignature)
                    inputIndex = inputIndex + 1
            else:
                while inputIndex < len(inputs):
                    client.startUntrustedTransaction(firstTransaction, inputIndex,
                                                                chipInputs, redeemScripts[inputIndex])
                    if changePath:
                        # we don't set meaningful outputAddress, amount and fees
                        # as we only care about the alternateEncoding==True branch
                        outputData = client.finalizeInput(b'', 0, 0, changePath, bfh(rawTx))
                    else:
                        outputData = client.finalizeInputFull(txOutput)
                    outputData['outputData'] = txOutput
                    if firstTransaction:
                        transactionOutput = outputData['outputData']
                    if outputData['confirmationNeeded']:
                        outputData['address'] = output
                        self.handler.finished()
                        pin = self.handler.get_auth( outputData ) # does the authenticate dialog and returns pin
                        if not pin:
                            raise UserWarning()
                        if pin != 'paired':
                            self.handler.show_message(_("Confirmed. Signing Transaction..."))
                    else:
                        # Sign input with the provided PIN
                        inputSignature = client.untrustedHashSign(inputsPaths[inputIndex],
                                                                             pin, lockTime=tx.locktime,
                                                                             version=tx.version,
                                                                             overwintered=tx.overwintered)
                        inputSignature[0] = 0x30 # force for 1.4.9+
                        signatures.append(inputSignature)
                        inputIndex = inputIndex + 1
                    if pin != 'paired':
                        firstTransaction = False
        except UserWarning:
            self.handler.show_error(_('Cancelled by user'))
            return
        except BTChipException as e:
            if e.sw == 0x6985:  # cancelled by user
                return
            elif e.sw == 0x6982:
                raise  # pin lock. decorator will catch it
            else:
                traceback.print_exc(file=sys.stderr)
                self.give_error(e, True)
        except BaseException as e:
            traceback.print_exc(file=sys.stdout)
            self.give_error(e, True)
        finally:
            self.handler.finished()

        for i, txin in enumerate(tx.inputs()):
            signingPos = inputs[i][4]
            txin['signatures'][signingPos] = bh2u(signatures[i])
        tx.raw = tx.serialize()

    @test_pin_unlocked
    @set_and_unset_signing
    def show_address(self, sequence, txin_type):
        client = self.get_client()
        address_path = self.get_derivation()[2:] + "/%d/%d"%sequence
        self.handler.show_message(_("Showing address ..."))
        try:
            client.getWalletPublicKey(address_path, showOnScreen=True)
        except BTChipException as e:
            if e.sw == 0x6985:  # cancelled by user
                pass
            elif e.sw == 0x6982:
                raise  # pin lock. decorator will catch it
            else:
                traceback.print_exc(file=sys.stderr)
                self.handler.show_error(e)
        except BaseException as e:
            traceback.print_exc(file=sys.stderr)
            self.handler.show_error(e)
        finally:
            self.handler.finished()

class LedgerPlugin(HW_PluginBase):
    libraries_available = BTCHIP
    keystore_class = Ledger_KeyStore
    client = None
    DEVICE_IDS = [
                   (0x2581, 0x1807), # HW.1 legacy btchip
                   (0x2581, 0x2b7c), # HW.1 transitional production
                   (0x2581, 0x3b7c), # HW.1 ledger production
                   (0x2581, 0x4b7c), # HW.1 ledger test
                   (0x2c97, 0x0000), # Blue
                   (0x2c97, 0x0001), # Nano-S
                   (0x2c97, 0x0004), # Nano-X
                   (0x2c97, 0x0005), # RFU
                   (0x2c97, 0x0006), # RFU
                   (0x2c97, 0x0007), # RFU
                   (0x2c97, 0x0008), # RFU
                   (0x2c97, 0x0009), # RFU
                   (0x2c97, 0x000a)  # RFU
                 ]
    VENDOR_IDS = (0x2c97, )
    LEDGER_MODEL_IDS = {
        0x10: "Ledger Nano S",
        0x40: "Ledger Nano X",
    }

    def __init__(self, parent, config, name):
        HW_PluginBase.__init__(self, parent, config, name)
        if self.libraries_available:
            # to support legacy devices and legacy firmwares
            self.device_manager().register_devices(self.DEVICE_IDS)
            # to support modern firmware
            self.device_manager().register_vendor_ids(self.VENDOR_IDS)

    def _recognize_device(cls, product_key):
        # legacy product_keys
        if product_key in cls.DEVICE_IDS:
            if product_key[0] == 0x2581:
                return True, "Ledger HW.1"
            if product_key == (0x2c97, 0x0000):
                return True, "Ledger Blue"
            if product_key == (0x2c97, 0x0001):
                return True, "Ledger Nano S"
            if product_key == (0x2c97, 0x0004):
                return True, "Ledger Nano X"
            return True, None
        # modern product_keys for Ledger device
        if product_key[0] == 0x2c97:
            product_id = product_key[1]
            model_id = product_id >> 8
            if model_id in cls.LEDGER_MODEL_IDS:
                model_name = cls.LEDGER_MODEL_IDS[model_id]
                return True, model_name
        # give up
        return False, None

    def can_recognize_device(self, device):
        return self._recognize_device(device.product_key)[0]

    def get_btchip_device(self, device):
        ledger = False
        if device.product_key[0] == 0x2581 and device.product_key[1] == 0x3b7c:
            ledger = True
        if device.product_key[0] == 0x2581 and device.product_key[1] == 0x4b7c:
            ledger = True
        if device.product_key[0] == 0x2c97:
            if device.interface_number == 0 or device.usage_page == 0xffa0:
                ledger = True
            else:
                return None  # non-compatible interface of a Nano S or Blue
        dev = hid.device()
        dev.open_path(device.path)
        dev.set_nonblocking(True)
        return HIDDongleHIDAPI(dev, ledger, BTCHIP_DEBUG)

    def create_client(self, device, handler):
        if handler:
            self.handler = handler

        client = self.get_btchip_device(device)
        if client is not None:
            client = Ledger_Client(client)
        return client

    def setup_device(self, device_info, wizard, purpose):
        devmgr = self.device_manager()
        device_id = device_info.device.id_
        client = devmgr.client_by_id(device_id)
        if client is None:
            # Workaround to show a user friendly message when no client object found
            raise Exception("Device is not in ZClassic mode")

        client.handler = self.create_handler(wizard)
        client.get_xpub("m/44'/147'", 'standard') # TODO replace by direct derivation once Nano S > 1.1

    def get_xpub(self, device_id, derivation, xtype, wizard):
        devmgr = self.device_manager()
        client = devmgr.client_by_id(device_id)
        client.handler = self.create_handler(wizard)
        client.checkDevice()
        xpub = client.get_xpub(derivation, xtype)
        return xpub

    def get_client(self, keystore, force_pair=True):
        # All client interaction should not be in the main GUI thread
        devmgr = self.device_manager()
        handler = keystore.handler
        with devmgr.hid_lock:
            client = devmgr.client_for_keystore(self, handler, keystore, force_pair)
        # returns the client for a given keystore. can use xpub
        #if client:
        #    client.used()
        if client is not None:
            client.checkDevice()
        return client

    def show_address(self, wallet, address):
        sequence = wallet.get_address_index(address)
        txin_type = wallet.get_txin_type(address)
        wallet.get_keystore().show_address(sequence, txin_type)

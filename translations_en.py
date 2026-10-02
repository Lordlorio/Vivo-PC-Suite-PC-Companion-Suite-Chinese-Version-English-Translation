# -*- coding: utf-8 -*-
"""Traductions anglaises des cles absentes de locales-en_US.js."""

CUR_L = '\u201c'
CUR_R = '\u201d'
PS = ['Plural', 'Singular']
TYPES = ['Audio', 'File', 'Image', 'Video']

FAMILY = {
    'FailFromCancelSend{t}{p}': '{0} cancelled the transfer. Failed to receive {2} {tl} from "' + '{1}' + '".',
    'FailFromNetWork{t}{p}': 'Network error. Failed to receive {1} {tl} from "' + '{0}' + '".',
    'FailFromUnKnown{t}{p}': 'Failed to receive {1} {tl} from "' + '{0}' + '".',
    'FailSendCancelReceive{t}{p}': '{0} cancelled receiving. Failed to send {1} {tl} to "' + '{2}' + '".',
    'FailSendNetWork{t}{p}': 'Network error. Failed to send {0} {tl} to "' + '{1}' + '".',
    'FailSendPhoneNoSpace{t}{p}': '{0} is out of storage space. Failed to send {1} {tl} to "' + '{2}' + '".',
    'FailSendUnKnown{t}{p}': 'Failed to send {0} {tl} to "' + '{1}' + '".',
    'FailSuccessFromCancel{t}': 'Cancelled. {T} from "' + '{0}' + '": {1} succeeded, {2} failed.',
    'FailSuccessFromNetWork{t}': 'Network error. {T} from "' + '{0}' + '": {1} succeeded, {2} failed.',
    'FailSuccessFromNoSpace{t}': 'The computer is out of storage space ({0} required). {T} from "' + '{1}' + '": {2} succeeded, {3} failed.',
    'FailSuccessSendCancel{t}': 'Cancelled. {T} to "' + '{0}' + '": {1} succeeded, {2} failed.',
    'FailSuccessSendNetWork{t}': 'Network error. {T} to "' + '{0}' + '": {1} succeeded, {2} failed.',
    'FailSuccessSendPhoneNoSpace{t}': '{0} is out of storage space. {T} to "' + '{1}' + '": {2} succeeded, {3} failed.',
    'FailSuccessTransNoSpace{t}': 'The computer is out of storage space ({0} required). {T} transferred to the computer: {1} succeeded, {2} failed.',
    'FailSuccessTransPhoneNoSpace{t}': '{0} is out of storage space. {T} transferred to {1}: {2} succeeded, {3} failed.',
}

TL = {'Audio': 'audio', 'File': 'file', 'Image': 'image', 'Video': 'video'}


def _gen_fail():
    out = {}
    for tpl, text in FAMILY.items():
        multi = '{p}' in tpl
        for typ in TYPES:
            names = [tpl.replace('{t}', typ)] if not multi else [tpl.replace('{t}', typ).replace('{p}', p) for p in PS]
            for name in names:
                val = text.replace('{T}', typ).replace('{tl}', TL[typ])
                out['fileManager.' + name] = val
    return out


EXPLICIT = {
    'connection.bi-ji-lian-xu-hu-tong1': 'Notes Continuity',

    'fileManager.ai-zhi-neng-shi-bie': 'AI recognition',
    'fileManager.bu-fen-wen-jian-guo-da': 'Some files are too large',
    'fileManager.chao-guo-chuan-shu-xian-liang': 'Transfer limit exceeded',
    'fileManager.chuan-shu-dao-shou-ji-ping-ban-noex': 'Transfer to phone/tablet',
    'fileManager.chuan-shu-qi-yu-wen-jian': 'Transfer remaining files',
    'fileManager.chuan-shu-shou-xian': 'Transfer restricted',
    'fileManager.dui-fang-yi-ju-jue': 'The other party declined',
    'fileManager.ji-xu-isopenfile': 'Continue viewing',
    'fileManager.ji-xu-isopenfile2': 'Continue transfer',
    'fileManager.jin-ri-bu-zai-ti-shi': "Don't show again today",
    'fileManager.ke-qian-wang-phonename-wen-jian-guan-li-android-data-tong-yi-shou-quan-hou-shua-xin':
        'Go to {0}"File Manager" > "Phone storage" > "Android" > "data", grant permission, then refresh',
    'fileManager.liu-liang-ti-xing': '{0} data usage reminder',
    'fileManager.live_photo_title': 'Live photo',
    'fileManager.office-kits-file-transfer': 'vivo Office Kit file transfer',
    'fileManager.phonename-wen-jian-guan-li-shou-quan-hou-ke-wan-zheng-cha-kan-ci-mu-lu-de-wen-jian':
        'After you grant {0}"File Manager" permission, you can view all files in this folder',
    'fileManager.ping-ban': 'Tablet',
    'fileManager.qian-wang-devicephonename-que-ren': 'Go to {0} to confirm',
    'fileManager.qing-qian-wang-phonename-wen-jian-guan-li-shou-quan':
        'Go to {0}"File Manager" to grant permission',
    'fileManager.qing-qiu-yi-chao-shi': 'Request timed out',
    'fileManager.qing-zai-devicephonename-shang-dian-ji-yun-xu': 'Tap "Allow" on {0}',
    'fileManager.que-ding-qing-kong-chuan-shu-dao-shou-ji-ping-ban-de-quan-bu-ji-lu-ma-noex':
        'Clear all transfer history for phone/tablet?',
    'fileManager.ru-xu-ji-xu-chuan-shu-qing-shi-yong-usb-lian-jie-gai-she-bei':
        'To continue transferring, connect the device via USB.',
    'fileManager.ru-xu-ji-xu-chuan-shu-qing-shi-yong-usb-lian-jie-gai-she-bei-2':
        'To continue transferring, connect the device via USB, then click "Save to computer".',
    'fileManager.usb-lian-jie': 'USB connection',
    'fileManager.wen-jian-guo-da': 'File too large',
    'fileManager.xi-tong-mu-lu-wen-jian-jia-bu-zhi-chi-cao-zuo': 'System folder operations are not supported',
    'fileManager.xiu-gai-shi-bai-reason': 'Failed to modify, {0}',
    'fileManager.xuan-ze-wen-jian-tai-duo-wu-fa-jin-hang-yun-chuan': 'Too many files selected for cloud transfer',
    'fileManager.yin-android-quan-xian-xian-zhi-zan-bu-zhi-chi-ci-gong-neng':
        'Not supported due to Android permission restrictions',
    'fileManager.yun-lian-jie-quan-sou':
        'You are connected via cloud. To keep your data safe, confirm access permission on {0} before searching.',
    'fileManager.yun-lian-tip-1':
        'You are connected via cloud. Only files smaller than {0} can be transferred. To transfer {2} larger files such as "{1}", connect the device via USB.',
    'fileManager.yun-lian-tip-2':
        'You are connected via cloud. Only files smaller than {0} can be transferred. To transfer "{1}", connect the device via USB.',
    'fileManager.yun-lian-tip-3':
        'You are connected via cloud. The daily transfer quota is {0} ({1} remaining), which is not enough to view this file. To continue, connect the device via USB.',
    'fileManager.yun-lian-tip-4':
        'You are connected via cloud. The daily transfer quota is {0} ({1} remaining), which is not enough to transfer the selected files. To continue, connect the device via USB.',
    'fileManager.yun-lian-tip-5':
        '{0} is using mobile data. Viewing this file over cloud connection will use {1} {2} of data. Continue viewing?',
    'fileManager.yun-lian-tip-6':
        '{0} is using mobile data. Transferring the selected files over cloud connection will use {1} {2} of data. Continue transferring?',
    'fileManager.yun-lian-tip-7':
        'Transferring files to third-party apps is restricted while connected via cloud. Save the file to the computer first, then import it into the third-party app.',
    'fileManager.yun-lian-tip-8':
        'You are connected via cloud. Only files smaller than {0} can be viewed. To access larger files, connect the device via USB.',
    'fileManager.yun-lian-tip-9':
        'You are connected via cloud. Only files smaller than {0} can be transferred. To transfer larger files, connect the device via USB.',
    'fileManager.yun-lian-tip-10':
        'You are connected via cloud. Up to 500 files can be transferred to {0} at a time.',

    'framework.cross-device-connect': 'Cross-device connectivity',
    'framework.mirror-fm-coor': 'Mirror your screen and manage or transfer files across devices for smoother collaboration',
    'framework.searchTablTitle14': 'Containing',
    'framework.searchTablTitle15': 'notes',

    'note.CliStatusLabel': 'Notes CLI service',
    'note.exportStageGenerating': 'Generating file...',
    'note.exportStageRendering': 'Formatting...',
    'note.exportStageWriting': 'Saving locally...',
    'note.goToCalendar': 'View in Calendar',
    'note.notShow': "Don't show again",
    'note.noteHistoryAsNewLoading': 'Saving',
    'note.noteToolbarParaHeadingTip': 'Heading',
    'note.noteToolbarParaIndentTip1': 'Increase indent',
    'note.noteToolbarParaOutdentTip': 'Decrease indent',
    'note.noteToolbarShareTo': 'Share',
    'note.todoChangeColorTitle': 'Change color',
    'note.todoMoveToCalendar': 'To-dos and their data have been moved to "Calendar"',
    'note.todoMoveToCalendarDesc': 'Manage schedules and to-dos together in Calendar for greater efficiency.',
    'note.viewDetails': 'View details',

    'record.FvMoveToRecentDeleteNotice': 'The selected recordings will be kept in Recently Deleted for 30 days.',
    'record.FvMoveToRecentDeleteOneNotice': 'This recording will be kept in Recently Deleted for 30 days.',
    'record.aiMark': 'Smart marker naming',
    'record.backSecond': 'Back {0}s',
    'record.deleteMark': 'Delete marker',
    'record.deleteMarkConfirmTitle': 'Delete this marker?',
    'record.deleteSingleNoteFromCloudTitle': 'Delete this recording from {0}?',
    'record.deleting': 'Deleting...',
    'record.exportInsight': 'Export insights',
    'record.exportOrganize': 'Export formatted text',
    'record.exportOriginal': 'Export original text',
    'record.exportSummary': 'Export summary',
    'record.export_insight': 'Insights',
    'record.export_original': 'Original text',
    'record.export_summary': 'Summary',
    'record.forwordSecond': 'Forward {0}s',
    'record.hideSpeakerTimestamp': 'Hide speaker and timestamps',
    'record.insightNoReplace': 'Insights cannot be replaced',
    'record.isAiRenameing': 'Naming with AI',
    'record.jumpMarkTime': 'Jump to marker',
    'record.loopPlay': 'Loop',
    'record.mark': 'Marker',
    'record.markList': 'Marker list',
    'record.markPlaceholder': 'Marker name',
    'record.pause': 'Pause',
    'record.permanentDeleting': 'Deleting permanently...',
    'record.permanentlyDelete': 'Delete permanently',
    'record.permanentlyRecordDel': 'Permanently delete this recording?',
    'record.permanentlyRecordDels': 'Permanently delete {0} recordings?',
    'record.photoMark': 'Image note',
    'record.play': 'Play',
    'record.playSetting': 'Playback settings',
    'record.playSettingInfo': 'Applies to a single recording only',
    'record.playSpeed': 'Playback speed',
    'record.previewBigPhoto': 'View full image',
    'record.quickMarkPlaceholder': 'Enter text',
    'record.recordAiTemplate': 'Choose an AI summary template',
    'record.recordAiTemplateSpeaker': 'Specify speaker',
    'record.recordAiTemplateSummary': "Generate an AI summary based on the selected speaker's content.",
    'record.recordNo': 'No recordings',
    'record.recordNotApplication': 'No app call recordings',
    'record.recordNotTelephone': 'No phone call recordings',
    'record.recordTemlateGenerate': 'Generate',
    'record.recoverBtn': 'Restore',
    'record.recovering': 'Restoring...',
    'record.recycleBinRetention30Days1New': 'Deleted files are kept for only 30 days, after which they are permanently deleted.',
    'record.removeMultiNoteFromCloudTitle': 'Delete {1} files from {0}?',
    'record.removeMultiRecordRecentlyTitle': 'Permanently delete the selected {0} recordings?',
    'record.removeMultiRecordTitle': 'Delete the selected {0} recordings?',
    'record.removeSingleRecordRecentlyTitle': 'Permanently delete this recording?',
    'record.removeSingleRecordTitle': 'Delete this recording?',
    'record.replacePhoto': 'Replace image',
    'record.searchInAllTabs': 'Search in all tabs',
    'record.searchInCurrentTab': 'Search in current tab',
    'record.searchScopeAll': 'All tabs',
    'record.searchScopeCurrent': 'Current tab',
    'record.showSpeakerTimestamp': 'Show speaker and timestamps',
    'record.skipSilent': 'Skip silent parts',
    'record.stopAiMark': 'Stop generating',
    'record.tabNameInsight': 'Insights',
    'record.tabNameMark': 'Markers',
    'record.tabNameSummary': 'Summary',
    'record.tabNameText': 'Transcript',
    'record.textMarkPlaceholder': 'Note this moment',
    'record.waitAiRename': 'Waiting for AI naming',
}


def build():
    d = {}
    d.update(_gen_fail())
    d.update(EXPLICIT)
    return d


if __name__ == '__main__':
    print('traductions construites:', len(build()))

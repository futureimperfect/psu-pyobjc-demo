#!/usr/bin/python

import os
import subprocess

from AppKit import *
import CoreFoundation
import Quartz

from pprint import pprint


# You need to define these constants for PyObjC < 2.3
# bit shiftyness
# Test with `import objc; objc.__version__
#
# NSApplicationPresentationDefault = 0
# NSApplicationPresentationAutoHideDock = 1 << 0
# NSApplicationPresentationHideDock = 1 << 1
# NSApplicationPresentationAutoHideMenuBar = 1 << 2
# NSApplicationPresentationHideMenuBar = 1 << 3
# NSApplicationPresentationDisableAppleMenu = 1 << 4
# NSApplicationPresentationDisableProcessSwitching = 1 << 5
# NSApplicationPresentationDisableForceQuit = 1 << 6
# NSApplicationPresentationDisableSessionTermination = 1 << 7
# NSApplicationPresentationDisableHideApplication = 1 << 8
# NSApplicationPresentationDisableMenuBarTransparency = 1 << 9
# NSApplicationPresentationFullScreen = 1 << 10
# NSApplicationPresentationAutoHideToolbar = 1 << 11


class Colors:
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'
    GREEN = '\033[92m'
    RED = '\033[91m'


def print_color(string, color=Colors.GREEN, bold=True):
    if isinstance(string, str):
        if bold:
            print Colors.BOLD + color + string + Colors.ENDC
        else:
            print color + string + Colors.ENDC


def block_user():
    '''
    Kiosk Mode

    Set Application Presentation Options.
    '''
    ws = NSWorkspace.sharedWorkspace()
    ws.hideOtherApplications()

    # OR'ing the desired options yields the correct result.
    options = NSApplicationPresentationHideDock | \
        NSApplicationPresentationDisableProcessSwitching | \
        NSApplicationPresentationDisableForceQuit | \
        NSApplicationPresentationDisableSessionTermination

    NSApp().setPresentationOptions_(options)


def unblock_user():
    '''
    Revert Application Presentation Options to the default.
    '''
    options = NSApplicationPresentationDefault

    NSApp().setPresentationOptions_(options)


def get_running_apps():
    ws = NSWorkspace.sharedWorkspace()
    running_apps = ws.runningApplications()
    apps = []
    for app in running_apps:
        apps.append(app.localizedName())
    apps = set(apps)

    return apps


def get_pref_val(key, domain):
    '''
    Returns the preference value for the specified key
    and preference domain.

    :param key: The preference key to get.
    :param domain: The preference domain to search.
    :returns: The preference value.
    '''
    if os.geteuid() == 0:
        console_user = get_console_user()
        cmd = '/usr/bin/python -c \'import CoreFoundation; print CoreFoundation.CFPreferencesCopyAppValue("%s", "%s")\'' % (
            key, domain)
        val = subprocess.check_output(['/usr/bin/su',
                                       '%s' % console_user,
                                       '-c',
                                       cmd])
    else:
        val = CoreFoundation.CFPreferencesCopyAppValue(key, domain)

    return val


def set_pref_val(key, data, domain):
    '''
    Sets the preference value (data) for the specified key
    and preference domain. It can set nested defaults such as:

    ManagedPlugInPolicies = {
        'com.oracle.java.JavaAppletPlugin': {
            'PlugInDisallowPromptBeforeUseDialog': False,
            'PlugInFirstVisitPolicy': 'PlugInPolicyAsk',
            'PlugInHostnamePolicies': ({
                'PlugInHostname': <some_hostname>,
                'PlugInPageURL': <some_uri>,
                'PlugInPolicy': 'PlugInPolicyAllowNoSecurityRestrictions',
                'PlugInRunUnsandboxed': True,
            })
        }
    }

    :param key: The preference key to set.
    :param data: The data which should be set for the specified key.
    :param domain: The preference domain which should be updated.
    '''
    if os.geteuid() == 0:
        console_user = get_console_user()
        cmd = '/usr/bin/python -c \'import CoreFoundation; CoreFoundation.CFPreferencesSetAppValue("%s", "%s", "%s")\'' % (
            key, data, domain)
        subprocess.check_output(['/usr/bin/su',
                                 '%s' % console_user,
                                 '-c',
                                 cmd])
    else:
        CoreFoundation.CFPreferencesSetAppValue(key, data, domain)

    # Synchronize defaults
    CoreFoundation.CFPreferencesAppSynchronize(domain)


def is_computer_locked():
    '''
    Quartz.CGSessionCopyCurrentDictionary()
    will return None if no UI session exists
    for the user that spawned the process,
    (e.g., root).

    :returns: True if the screen is locked.
    '''
    ret = False
    if os.geteuid() == 0:
        console_user = get_console_user()
        cmd = '/usr/bin/python -c \'import Quartz; print Quartz.CGSessionCopyCurrentDictionary()\''
        d = subprocess.check_output(['/usr/bin/su',
                                     '%s' % console_user,
                                     '-c',
                                     cmd])
        not_on_console = 'kCGSSessionOnConsoleKey = 0'
        screen_is_locked = 'CGSSessionScreenIsLocked = 1'
        if not_on_console in d or screen_is_locked in d:
            ret = True
    else:
        d = Quartz.CGSessionCopyCurrentDictionary()
        if d.get('kCGSSessionOnConsoleKey') is False or d.get(
                'CGSSessionScreenIsLocked') is True:
            ret = True

    return ret


def get_console_user():
    '''
    :returns: The currently logged in user as a string.
    '''
    if os.geteuid() == 0:
        console_user = subprocess.check_output(['/usr/bin/stat',
                                                '-f%Su',
                                                '/dev/console']).strip()
    else:
        import getpass
        console_user = getpass.getuser()

    return console_user


def get_finder_sidebar_item_names():
    '''
    :returns: A list of the items in the user's Finder Sidebar.
    '''
    names = []
    custom_list_items = get_pref_val(
        'favoriteitems',
        'com.apple.sidebarlists').get(
        'CustomListItems')
    for item in custom_list_items:
        name = item.get('Name')
        if name:
            names.append(name)
    return names


def main():
    # Check if the computer is locked.
    print_color('Computer locked:')
    print('\t%s' % is_computer_locked())
    print

    # Turn on kiosk mode
    block_user()
    print_color("You're blocked!")
    print

    # Get some preferences.
    keys_to_domains = {
        'UserStyleSheetEnabled': 'com.apple.safari',
        'menuExtras': 'com.apple.systemuiserver',
        'SendDoNotTrackHTTPHeader': 'com.apple.safari'
    }
    print_color('Some Preferences:')
    for key, domain in keys_to_domains.items():
        val = get_pref_val(
            key,
            domain
        )
        print_color(
            '\t%s (%s):' % (key, domain),
            color=Colors.BLUE,
            bold=False
        )
        if not isinstance(val, (int, bool, str, unicode, float, long)):
            pprint(val)
        else:
            print('\t\t%s' % val)
    print

    # Set a preference.
    set_pref_val(
        'SendDoNotTrackHTTPHeader',
        True,
        'com.apple.safari'
    )

    # Print Finder sidebar items.
    sidebar_items = get_finder_sidebar_item_names()
    print_color('Finder Sidebar Items:')
    for item in sidebar_items:
        print('\t' + item)
    print

    # Check if the 'askForPassword' preference is managed.
    ask_for_password_managed = CoreFoundation.CFPreferencesAppValueIsForced(
        'askForPassword',
        'com.apple.screensaver'
    )
    print_color('Managing the screensaver askForPassword preference:')
    print('\t%s' % ask_for_password_managed)
    print

    # Show the currently running applications.
    running_apps = get_running_apps()
    print_color('Running Applications:')
    for app in running_apps:
        print('\t' + app)
    print

    # Turn off kiosk mode.
    print_color('Unblocking.')
    unblock_user()


if __name__ == '__main__':
    main()

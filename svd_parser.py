# xml to dictionary parser
import xmltodict
# argv
import sys
# regex
import re
# path checking
import os
# deepcopy() of nested dicts
import copy


argv = sys.argv
argc = len(argv)

if argc != 3:
   print('ERROR: argc != 2', file=sys.stderr)
   exit(-1)

f         = os.path.abspath(argv[1])
user_peri = argv[2]

if not os.path.isfile(f):
   print('ERROR: file "%s" doesn\'t exist' %(f), file=sys.stderr)
   exit(-1)

f = open(f, 'r')
lines = f.read()
f.close()

f = xmltodict.parse(lines)

# dictionary of all peripherals
peri = {}

# foreach peripheral
for p in f['device']['peripherals']['peripheral']:
   # if it has only 1 peripheral
   if not isinstance(p, dict):
      p = f['device']['peripherals']['peripheral']

   peri_name = p['name']

   # each peripheral name is a dict
   peri[peri_name] = {}

   peri[peri_name]['base'] = p['baseAddress']

   # each peripheral has an IRQ dict
   peri[peri_name]['irq']  = {}

   # each peripheral has a reg dict
   peri[peri_name]['reg']  = {}

   # if peripheral has interrupts
   if 'interrupt' in p:
      # foreach IRQ
      for irq in p['interrupt']:
         # if it has only 1 IRQ
         if not isinstance(irq, dict):
            irq = p['interrupt']

         irq_name = irq['name']

         # each IRQ name is a dict
         peri[peri_name]['irq'][irq_name] = {}

         # +16 because the processor has 16 core interrupts
         peri[peri_name]['irq'][irq_name]['number'] = str(16 + int(irq['value']))
         peri[peri_name]['irq'][irq_name]['desc'] = re.sub(r'\s+', ' ', irq['description'].strip())

   # if it's a derived (shadow) peripheral
   if '@derivedFrom' in p:
      # deep/recursive copy the deriving module
      peri[peri_name] = copy.deepcopy(peri[p['@derivedFrom']])

      # change specific attributes and remove the field dict since it's repeated
      peri[peri_name]['base'] = p['baseAddress']

      for reg_name in peri[peri_name]['reg']:
         peri[peri_name]['reg'][reg_name]['field'] = {}

   # if it's a deriving peripheral
   else:
      peri[peri_name]['desc']  = p['description']
      peri[peri_name]['group'] = p['groupName']

      # foreach reg in the peripheral
      for reg in p['registers']['register']:
         # if it has only 1 reg
         if not isinstance(reg, dict):
            reg = p['registers']['register']

         reg_name = reg['name']

         # each register name is a dict
         peri[peri_name]['reg'][reg_name] = {}

         # each register has a bitfield dict
         peri[peri_name]['reg'][reg_name]['field'] = {}

         peri[peri_name]['reg'][reg_name]['desc']     = re.sub(r'\s+', ' ', reg['description'].strip())
         peri[peri_name]['reg'][reg_name]['offset']   = reg['addressOffset']
         peri[peri_name]['reg'][reg_name]['resetVal'] = reg['resetValue']

         # foreach bitfield in the register
         for field in reg['fields']['field']:
            # if it has only 1 bitfield
            if not isinstance(field, dict):
               field = reg['fields']['field']

            field_name = field['name']

            # each bitfield name in the register is a dict
            peri[peri_name]['reg'][reg_name]['field'][field_name] = {}

            peri[peri_name]['reg'][reg_name]['field'][field_name]['desc']   = re.sub(r'\s+', ' ', field['description'].strip())
            peri[peri_name]['reg'][reg_name]['field'][field_name]['offset'] = field['bitOffset']
            peri[peri_name]['reg'][reg_name]['field'][field_name]['width']  = field['bitWidth']


print('Found peripherals:')
print('{')
for peri_name in peri:
   print('  ' + peri_name)
print('}')
print('count = %s\n' %(str(len(peri))))

if not user_peri in peri:
   print('ERROR: peripheral "%s" doesn\'t exist' %(user_peri), file=sys.stderr)
   exit(-1)

fc = open('%s.c' %(peri[user_peri]['group']), 'a')
fh = open('%s.h' %(peri[user_peri]['group']), 'a')

# if file is empty
if os.path.getsize(fc.name) == 0:
   fc.write("/* libs */\n")
   fc.write("#include <stdint.h>\n")
   fc.write("/* own */\n")
   fc.write("#include \"%s.h\"\n" %(peri[user_peri]['group']))

fc.write('\n')
fc.write("\n")
fc.write("/* ############################################### */\n")
fc.write("/* base address of the module \"%s\" */\n" %(user_peri))
fc.write("#define %s_BASE_ADDR (%s)\n" %(user_peri, peri[user_peri]['base']))

for reg_name in peri[user_peri]['reg']:
   reg = peri[user_peri]['reg'][reg_name]

   fc.write('\n')
   fc.write('/* === === === === === === === === === === === === */\n')
   fc.write("/* base address and masks for register: %s.%s (%s), reset value = %s */\n" %(user_peri, reg_name, reg['desc'], reg['resetVal']))
   fc.write("#define %s_%s (*((volatile uint32_t*)(%s_BASE_ADDR + %s)))\n" %(user_peri, reg_name, user_peri, reg['offset']))

   for bitfield_name in reg['field']:
      bitfield = reg['field'][bitfield_name]

      # create a mask by the following sequence:
      # 1- mask = train of 1's
      # 2- add 0's from the right by an amount = bitWidth
      # 3- left shift these 0's by an amount = bitOffset
      #   a- left shift 1 step
      #   b- or with 1
      #   b- iterate by an amount = bitOffset
      field_mask = 0xFFFFFFFF
      field_mask = field_mask << int(bitfield['width'])
      for i in range(0, int(bitfield['offset'])):
         field_mask = (field_mask << 1 | 1) & 0xFFFFFFFF

      field_mask = ~field_mask & 0xFFFFFFFF
      # format the mask as a 4-byte uppercase hex value
      field_mask = "0x{0:0{1}X}".format(field_mask, 8)

      fc.write("/* mask for bitfield \"%s.%s\" (%s) */\n" %(reg_name, bitfield_name, bitfield['desc']))
      fc.write("#define %s_%s_MASK (%s)\n" %(reg_name, bitfield_name, field_mask))
   
   fc.write('/* === === === === === === === === === === === === */\n')

fc.write("/* ############################################### */\n")

if len(peri[user_peri]['irq']) > 0:
   fc.write("\n")
   fc.write("/* Peripheral \"%s\" has the following IRQs:\n" %(user_peri))

   for irq_name in peri[user_peri]['irq']:
      irq = peri[user_peri]['irq'][irq_name]
      fc.write(" *    IRQ #%s: %s\n" %(irq['number'], irq['desc']))

   fc.write(" */\n")

fc.close()
fh.close()

import time
from random import randrange
from threading import Thread

import requests

from api_client import ApiObject, CONTAINER_ROOT_URL, MATERIAL_ROOT_URL


def create_plate():
    parent_labware = ApiObject(root=CONTAINER_ROOT_URL, type='labwares', attributes={'barcode_prefix': 'TEST', 'barcode_info': 'XYZ', 'external_id': str(randrange(0, 1000000000))},
                               relationships={'labware_type': ApiObject(type='labware_types', attributes={'name': 'generic 384 well plate'})})
    parent_labware.save()

    parent_material_batch = ApiObject(root=MATERIAL_ROOT_URL, type='material_batches', attributes={'name': 'stamping_test_parent'}, relationships={
        'materials': [ApiObject(type='materials', attributes={'name': parent_labware.get('barcode') + '_' + receptacle.get('location').get('name')},
                                relationships={'material_type': ApiObject.find(MATERIAL_ROOT_URL, 'material_types', 1).load(),
                                               'metadata': [ApiObject(type='metadata', attributes={'key': 'metadata %s %s' % (n, m), 'value': str(randrange(0, 10000000))}) for m in range(3)]}) for
                      (n, receptacle) in
                      enumerate(parent_labware.get('receptacles'))]})
    parent_material_batch.save()

    for receptacle, material in zip(parent_labware.get('receptacles'), parent_material_batch.get('materials')):
        receptacle.set('material_uuid', material.id)
    parent_labware.save()

    return parent_labware.get('barcode')


def stamp(barcode):
    start_time = time.time()
    labware = ApiObject.find_by(CONTAINER_ROOT_URL, 'labwares', {'barcode': barcode})

    get_labware_time = time.time()

    new_labware = ApiObject(root=CONTAINER_ROOT_URL, type='labwares', attributes={'barcode_prefix': 'TEST', 'barcode_info': 'XYZ', 'external_id': str(randrange(0, 1000000000))},
                            relationships={'labware_type': labware.get('labware_type')})
    new_labware.save()

    new_labware_time = time.time()

    sample_uuids = [receptacle.get('material_uuid') for receptacle in labware.get('receptacles')]

    material_batch = ApiObject(root=MATERIAL_ROOT_URL, type='material_batches', relationships={'materials': [ApiObject(type='materials', id=sample_uuid) for sample_uuid in sample_uuids]})
    material_batch.save()

    get_materials_time = time.time()

    new_materials = [
        ApiObject(root=material.root, type='materials', attributes={
            'name': new_labware.get('barcode') + '_' + [receptacle.get('location').get('name') for receptacle in labware.get('receptacles') if receptacle.get('material_uuid') == material.id][0]},
                  relationships={'metadata': material.get('metadata') or [], 'material_type': material.get('material_type'), 'parents': [material]}) for
        material in material_batch.get('materials')]

    new_batch = ApiObject(root=MATERIAL_ROOT_URL, type='material_batches', relationships={'materials': new_materials})
    new_batch.save()

    save_materials_time = time.time()

    child = {material.get('parents')[0].id: material.id for material in new_batch.get('materials')}
    receptacles = [ApiObject(root=CONTAINER_ROOT_URL, type='receptacles', attributes={'material_uuid': child[receptacle.get('material_uuid')]}, relationships=receptacle.relationships()) for receptacle
                   in labware.get('receptacles')]

    new_labware.set('receptacles', receptacles)
    new_labware.save()

    end_time = time.time()

    # print("Get labware =", get_labware_time - start_time)
    # print("Empty labware =", new_labware_time - get_labware_time)
    # print("Get materials =", get_materials_time - new_labware_time)
    # print("New materials =", save_materials_time - get_materials_time)
    # print("Update labware =", end_time - save_materials_time)
    # print("Total =", end_time - start_time)


def stamp_four():
    first_labwares = requests.get(CONTAINER_ROOT_URL + 'labwares').json()
    try:
        last_labwares = requests.get(first_labwares['links']['last']).json()
    except KeyError:
        last_labwares = first_labwares
    barcodes = [labware['attributes']['barcode'] for labware in last_labwares['data'][-4:]]

    if len(barcodes) < 4:
        prev_labware = requests.get(last_labwares['links']['prev']).json()

        i = len(prev_labware['data']) - 1

        while len(barcodes) < 4:
            barcodes.append(prev_labware['data'][i]['attributes']['barcode'])
            i -= 1

    if len(barcodes) < 4:
        raise Exception("Not enough barcodes")

    start_time = time.time()
    labwares = [ApiObject.find_by(CONTAINER_ROOT_URL, 'labwares', {'barcode': barcode}) for barcode in barcodes]

    get_labware_time = time.time()

    new_labwares = []
    for labware in labwares:
        new_labware = ApiObject(root=CONTAINER_ROOT_URL, type='labwares', attributes={'barcode_prefix': 'TEST', 'barcode_info': 'XYZ', 'external_id': str(randrange(0, 1000000000))},
                                relationships={'labware_type': labware.get('labware_type')})
        new_labware.save()
        new_labwares.append(new_labware)

    new_labware_time = time.time()

    sample_uuids = [receptacle.get('material_uuid') for labware in labwares for receptacle in labware.get('receptacles')]

    material_batch = ApiObject(root=MATERIAL_ROOT_URL, type='material_batches', relationships={'materials': [ApiObject(type='materials', id=sample_uuid) for sample_uuid in sample_uuids]})
    material_batch.save()
    materials = {material.id: material for material in material_batch.get('materials')}

    get_materials_time = time.time()

    new_materials = []
    for (labware, new_labware) in zip(labwares, new_labwares):
        for receptacle in labware.get('receptacles'):
            material = materials[receptacle.get('material_uuid')]
            new_materials.append(ApiObject(root=material.root, type='materials', attributes={
                'name': new_labware.get('barcode') + '_' + [receptacle.get('location').get('name') for receptacle in labware.get('receptacles') if receptacle.get('material_uuid') == material.id][0]},
                                           relationships={'metadata': material.get('metadata') or [], 'material_type': material.get('material_type'), 'parents': [material]}))

    new_batch = ApiObject(root=MATERIAL_ROOT_URL, type='material_batches', relationships={'materials': new_materials})
    new_batch.save()

    save_materials_time = time.time()

    child = {material.get('parents')[0].id: material.id for material in new_batch.get('materials')}

    for (labware, new_labware) in zip(labwares, new_labwares):
        receptacles = [ApiObject(root=CONTAINER_ROOT_URL, type='receptacles', attributes={'material_uuid': child[receptacle.get('material_uuid')]}, relationships=receptacle.relationships()) for
                       receptacle in labware.get('receptacles')]

        new_labware.set('receptacles', receptacles)
        new_labware.save()

    end_time = time.time()
    #
    # print("Get labware =", get_labware_time - start_time)
    # print("Empty labware =", new_labware_time - get_labware_time)
    # print("Get materials =", get_materials_time - new_labware_time)
    # print("New materials =", save_materials_time - get_materials_time)
    # print("Update labware =", end_time - save_materials_time)
    # print("Total =", end_time - start_time)


if __name__ == '__main__':
    barcode = create_plate()

    print("One plate")
    start_time = time.time()
    stamp(barcode)
    end_time = time.time()

    print(end_time - start_time)

    barcodes = [create_plate() for x in range(4)]
    print("Four plates")

    start_time = time.time()

    threads = []
    for barcode in barcodes:
        thr = Thread(target=stamp, args=[barcode])
        thr.start()
        threads.append(thr)

    for thread in threads:
        thread.join()

    end_time = time.time()

    print(end_time - start_time)

    # for i in range(3):
    #     create_plate()
    # print("Four plates")
    # stamp_four()

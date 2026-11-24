/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_1191203989")

  // update collection data
  unmarshal({
    "createRule": "@request.auth.id != ''",
    "deleteRule": "@request.auth.id != ''",
    "listRule": "@request.auth.id != ''",
    "updateRule": "@request.auth.id != ''",
    "viewRule": "@request.auth.id != ''"
  }, collection)

  // add field
  collection.fields.addAt(1, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_27982692",
    "hidden": false,
    "id": "relation1051609613",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "farmacia",
    "presentable": false,
    "required": true,
    "system": false,
    "type": "relation"
  }))

  // add field
  collection.fields.addAt(2, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text27834329",
    "max": 0,
    "min": 0,
    "name": "fecha",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": true,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(3, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text3885459298",
    "max": 0,
    "min": 0,
    "name": "turno",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_1191203989")

  // update collection data
  unmarshal({
    "createRule": "@request.auth.role = 'farmacia' || @request.auth.role = 'admin'",
    "deleteRule": "@request.auth.role = 'admin'",
    "listRule": "@request.auth.role = 'admin' || @request.auth.id != ''",
    "updateRule": "@request.auth.role = 'farmacia' || @request.auth.role = 'admin'",
    "viewRule": "@request.auth.role = 'admin' || @request.auth.id != ''"
  }, collection)

  // remove field
  collection.fields.removeById("relation1051609613")

  // remove field
  collection.fields.removeById("text27834329")

  // remove field
  collection.fields.removeById("text3885459298")

  return app.save(collection)
})

/**
 * Triggered from a message on a Cloud Pub/Sub topic.
 *
 * @param {!Object} event The Cloud Functions event.
 * @param {!Function} The callback function.
 */
exports.subscribe =  (event, callback) => {

  const pubsubMessage = event.data;
  const payload = Buffer.from(pubsubMessage, 'base64').toString();
  console.log(payload);
  var json_obj = JSON.parse(payload);
  var insert_obj = {
    insertId: json_obj.DATETIME,
    json: json_obj
  };
  const options = {
  raw: true
  };
  //----------------------------
  // insert
  //----------------------------
  const {BigQuery} = require('@google-cloud/bigquery');
  const bigquery = new BigQuery({ projectId: 'electric-238022' });
  
  var table_name = 'TBL_'+json_obj.TYPE;
  
  console.log(table_name);
  console.log(insert_obj);

  bigquery
    .dataset('DATASET')
    .table(table_name)
    .insert(insert_obj, options)

  .then(function(result) {

    console.log('BQ INSERTED : ' + payload);
    callback();
  })
  .catch((err) => {
    console.error('BQ ERROR : ', err);
    callback(1);
  });
};
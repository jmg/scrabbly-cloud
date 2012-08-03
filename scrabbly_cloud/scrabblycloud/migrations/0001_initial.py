# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Tile'
        db.create_table('scrabblycloud_tile', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('x', self.gf('django.db.models.fields.PositiveIntegerField')(null=True)),
            ('y', self.gf('django.db.models.fields.PositiveIntegerField')(null=True)),
            ('letter', self.gf('django.db.models.fields.CharField')(max_length=1)),
        ))
        db.send_create_signal('scrabblycloud', ['Tile'])

        # Adding model 'Player'
        db.create_table('scrabblycloud_player', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['auth.User'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=500)),
            ('remote_id', self.gf('django.db.models.fields.CharField')(max_length=100)),
        ))
        db.send_create_signal('scrabblycloud', ['Player'])

        # Adding model 'PlayerBoard'
        db.create_table('scrabblycloud_playerboard', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('player', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['scrabblycloud.Player'])),
            ('Board', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['scrabblycloud.Board'])),
            ('points', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('scrabblycloud', ['PlayerBoard'])

        # Adding M2M table for field tiles on 'PlayerBoard'
        db.create_table('scrabblycloud_playerboard_tiles', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('playerboard', models.ForeignKey(orm['scrabblycloud.playerboard'], null=False)),
            ('tile', models.ForeignKey(orm['scrabblycloud.tile'], null=False))
        ))
        db.create_unique('scrabblycloud_playerboard_tiles', ['playerboard_id', 'tile_id'])

        # Adding model 'Board'
        db.create_table('scrabblycloud_board', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('height', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('width', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal('scrabblycloud', ['Board'])

        # Adding M2M table for field tiles on 'Board'
        db.create_table('scrabblycloud_board_tiles', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('board', models.ForeignKey(orm['scrabblycloud.board'], null=False)),
            ('tile', models.ForeignKey(orm['scrabblycloud.tile'], null=False))
        ))
        db.create_unique('scrabblycloud_board_tiles', ['board_id', 'tile_id'])


    def backwards(self, orm):
        # Deleting model 'Tile'
        db.delete_table('scrabblycloud_tile')

        # Deleting model 'Player'
        db.delete_table('scrabblycloud_player')

        # Deleting model 'PlayerBoard'
        db.delete_table('scrabblycloud_playerboard')

        # Removing M2M table for field tiles on 'PlayerBoard'
        db.delete_table('scrabblycloud_playerboard_tiles')

        # Deleting model 'Board'
        db.delete_table('scrabblycloud_board')

        # Removing M2M table for field tiles on 'Board'
        db.delete_table('scrabblycloud_board_tiles')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'scrabblycloud.board': {
            'Meta': {'object_name': 'Board'},
            'height': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'players': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['scrabblycloud.Player']", 'through': "orm['scrabblycloud.PlayerBoard']", 'symmetrical': 'False'}),
            'tiles': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['scrabblycloud.Tile']", 'symmetrical': 'False'}),
            'width': ('django.db.models.fields.PositiveIntegerField', [], {})
        },
        'scrabblycloud.player': {
            'Meta': {'object_name': 'Player'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'remote_id': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'scrabblycloud.playerboard': {
            'Board': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['scrabblycloud.Board']"}),
            'Meta': {'object_name': 'PlayerBoard'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'player': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['scrabblycloud.Player']"}),
            'points': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'tiles': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['scrabblycloud.Tile']", 'symmetrical': 'False'})
        },
        'scrabblycloud.tile': {
            'Meta': {'object_name': 'Tile'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'letter': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'x': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'y': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'})
        }
    }

    complete_apps = ['scrabblycloud']
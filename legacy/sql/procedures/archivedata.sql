-- SqlProcedure: [dbo].[archivedata]
-- header:
-- CREATE proc [dbo].[archivedata]

CREATE proc [dbo].[archivedata]
as
set nocount on 


	declare archcur cursor for
		select stockID, atwhen,price,volume,dayhigh,daylow,rawhigh,rawlow,rawprice,rawvolume,changefromlast,datasource from stockdata where atwhen < dateadd(year,-3,getdate())

	declare @stockID int, @atwhen datetime, @price money, @volume bigint, @dayhigh money, @daylow money, @rawhigh money, @rawlow money, @rawprice money, @rawvolume bigint,@change decimal(5,2), @datasource int

	open archcur
	fetch next from archcur into @stockID, @atwhen, @price, @volume, @dayhigh, @daylow, @rawhigh, @rawlow, @rawprice, @rawvolume, @change, @datasource
	while @@fetch_status=0
		begin

		if not exists (select * from stockdataarchive where stockID=@stockID and atwhen=@atwhen)
			begin
				insert into stockdataarchive(stockID, atwhen,price,volume,dayhigh,daylow,rawhigh,rawlow,rawprice,rawvolume,changefromlast,datasource)
					values(@stockID, @atwhen, @price, @volume, @dayhigh, @daylow, @rawhigh, @rawlow, @rawprice, @rawvolume, @change, @datasource)
				
			end
			
		delete from stockdata
		where stockID=@stockID and atwhen =@atwhen

		fetch next from archcur into @stockID, @atwhen, @price, @volume, @dayhigh, @daylow, @rawhigh, @rawlow, @rawprice, @rawvolume, @change, @datasource
		end
	close archcur
	deallocate archcur

	/*
	insert into stockdataarchive
		select * from stockdata
		where atwhen < dateadd(year,-3,getdate())


	delete from stockdata
	where atwhen < dateadd(year,-3,getdate())

	*/

	ALTER INDEX [PK_StockData] ON [dbo].[StockData] REBUILD WITH ( PAD_INDEX  = OFF, STATISTICS_NORECOMPUTE  = OFF, ALLOW_ROW_LOCKS  = ON, ALLOW_PAGE_LOCKS  = ON, SORT_IN_TEMPDB = OFF, ONLINE = OFF )

	ALTER INDEX [PK_SID] ON [dbo].[StockData] REBUILD WITH ( PAD_INDEX  = OFF, STATISTICS_NORECOMPUTE  = OFF, ALLOW_ROW_LOCKS  = ON, ALLOW_PAGE_LOCKS  = OFF, SORT_IN_TEMPDB = OFF, ONLINE = OFF )

set nocount off

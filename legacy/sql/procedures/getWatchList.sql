-- SqlProcedure: [dbo].[getWatchList]

set nocount on


if @StartDate = null
	begin
		select s.stockID, s.ticker, s.companyname, s.exchange, s.lastprice, s.lastvolume, hp.atwhen Joined, max(sd.price) [52WH] from holdingpen hp
		inner join stock s on s.stockID = hp.stockID
		inner join stockdata sd on sd.stockID = s.stockID
		where code = @code
		and sd.atwhen > dateadd(year,-1,getdate())
		group by s.stockID, s.ticker, s.companyname,s.exchange, s.lastprice, s.lastvolume, hp.atwhen 
		order by s.companyname asc
	end
else
	begin
		select s.stockID, s.ticker, s.companyname, s.exchange, s.lastprice, s.lastvolume, hp.atwhen Joined, max(sd.price) [52WH] from holdingpen hp
		inner join stock s on s.stockID = hp.stockID
		inner join stockdata sd on sd.stockID = s.stockID
		where code = @code
		and sd.atwhen >= @startdate
		group by s.stockID, s.ticker, s.companyname,s.exchange, s.lastprice, s.lastvolume, hp.atwhen 
		order by s.companyname asc
	end

set nocount off

-- SqlProcedure: [dbo].[addMember]

set nocount on

	if exists (select * from Member where email = @Email)
		begin
			select -1
		end
	else
		begin
			insert into Member (FirstName, Lastname, Email, Password, AtWhenSubscribe, BirthYear, Gender)
				select @firstname, @lastname, @email, @password, getdate(), @BirthYear, @Gender

			select @@IDENTITY
		end

set nocount off
